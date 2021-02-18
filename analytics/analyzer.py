import traceback
from collections import defaultdict
from pathlib import Path

import pandas as pd
from pygount import SourceAnalysis
from django.db.models import Max, F
from django.utils.timezone import make_aware, is_aware
from pygount.analysis import SourceState

from analytics.blames import update_blame_object, calc_total_ins_and_dels
from analytics.bulk import BulkCreateManager, BulkUpdateManager
from authentication.models import User
from commits.models import Commit, CommitBlame
from developers.models import Developer, Blame
from files.models import File, FilePath, FileChange, FileBlame, FileKnowledge
from git_interface.gitobjects import GitRepository
from analytics.complexity import calculate_complexity_in
from repos.models import Repository, Branch
import logging

from tools.encoding import detect_encoding

_log_pygount = logging.getLogger('pygount')
_log_pygount.disabled = True
logger = logging.getLogger(__name__)


def language_is_code(lang):
    return lang not in ('__unknown__', '__binary__', '__error__', '__generated__', '__empty__')


def process_repo_objects(repo: Repository):
    logger.info("processing repo: {}".format(repo))
    analyzer = RepoAnalyzer(repo)
    analyzer.process()


BULK_SIZE = 500


class RepoAnalyzer(object):
    count_change_status = 0

    def __init__(self, repo: Repository):
        self.repo: Repository = repo
        self.owner: User = repo.owner
        self.filepath_cache = dict()
        self.file_cache = dict()
        self.git_repo = GitRepository(self.repo.base_directory)
        self.developer_cache = dict()
        self.count_change_status = 0
        self.dict_change_status = dict()

        rbts = self.repo.branches_to_track.strip()
        if rbts == '':
            self.remote_branches_to_track = [self.repo.default_branch if self.repo.default_branch else 'master']
        else:
            self.remote_branches_to_track = rbts.replace(';', ',').replace(' ', ',').split(',')

        self.current_branch = self.repo.default_branch

    def process(self):
        self.repo.status = Repository.Status.ANALYZING
        self.repo.save()
        self.file_cache = dict()
        self.dict_change_status = dict()
        for branch in self.remote_branches_to_track:
            if self.repo.default_branch == '':
                self.repo.default_branch = branch
                self.repo.save()

            self.process_branch(branch)

        if self.repo.default_branch > '':
            self.git_repo.checkout(self.repo.default_branch)

    def process_branch(self, branch_name: str):
        logger.info("CHECKOUT BRANCH {}".format(branch_name))
        if not self.git_repo.checkout(branch_name):
            return None

        branch, created = Branch.objects.get_or_create(name=branch_name, repository=self.repo)
        logger.info('BRANCH %s CREATED: %s', branch_name, created)

        self.dict_change_status = dict()

        self.create_commits(branch)
        self.__process_files_hotspot_weight(branch)
        with BulkCreateManager(Blame) as blames:
            for author in self.developer_cache.values():
                blames.add(Blame(author=author, repository=self.repo, branch=branch, loc=0))
        self.process_fileknowledge(branch)
        self.process_blames(branch)
        return branch

    def create_commits(self, branch: Branch):
        commit_history = self.git_repo.get_commits(branch=branch.name)

        logger.info('BEGIN COMMIT HISTORY')
        commit_dict = {}
        with BulkCreateManager(Commit, chunk_size=2000) as bulk:
            for commit in commit_history:
                author_email = commit.author.email
                author = self.__get_or_create_author(author_email, commit.author.name)
                c = self.create_commit(commit, author, branch)
                commit_dict[commit] = c
                if bulk.add(c):
                    self.file_creation(commit_dict, branch)
                    commit_dict = {}
        self.file_creation(commit_dict, branch)
        logger.info("END COMMIT HISTORY")

    def file_creation(self, commit_dict, branch):
        logger.info("BEGIN FILE CREATION")
        for git_commit in commit_dict.keys():
            self.create_files(branch, git_commit.stats.files)
        logger.info("END FILE CREATION")

        logger.info("BEGIN FILE CHANGES CREATION")
        with BulkCreateManager(FileChange, chunk_size=1000) as bulk:
            with BulkCreateManager(FileBlame, chunk_size=1000) as blames:
                for (git_commit, commit) in commit_dict.items():
                    self.create_file_changes(branch, git_commit.stats.files, commit, git_commit, bulk, blames)
        logger.info("END FILE CHANGES CREATION")

    def create_files(self, branch, files):
        with BulkCreateManager(File, chunk_size=1000) as cf:
            with BulkUpdateManager(File, ['changes'], chunk_size=1000) as uf:
                for fn in files.keys():
                    file, created = self.create_file(fn, branch)
                    file.changes += 1
                    if created:
                        cf.add(file)
                    else:
                        uf.add(file)

    def create_file_changes(self, branch, files, commit, git_commit, bulk, blames):
        for fn in files.keys():
            file = self.file_cache[self.get_file_key(fn, branch)]
            fc = self.create_file_change_object(commit, file, files[fn], git_commit)
            bulk.add(fc)
            if file.exists and file.is_code and fc.change_type in ['A', 'M'] or fc.change_type == '':
                blame = self.create_file_blame_object(fn, commit, file)
                if blame:
                    blames.add(blame)

    def process_fileknowledge(self, branch: Branch):
        logger.info("FILE KNOWLEDGE PROCESSING")

        index = list(File.objects.filter(repository=self.repo, branch=branch).values_list('id', flat=True))
        authors_id = set(Commit.objects.order_by('author').values_list('author', flat=True).distinct())
        df = pd.DataFrame(0, index=index, columns=authors_id)

        file_knowledge_dict = dict()
        sum_file_knowledge_dict = defaultdict(int)

        file_owners = dict()
        with BulkCreateManager(CommitBlame, chunk_size=1000) as bulk:
            for c in Commit.objects.filter(branch=branch, repository=self.repo).select_related("author").order_by(
                    "date"):
                if c.is_merge:
                    continue
                author = c.author

                add_others = 0
                add_self = 0
                del_self = 0
                del_others = 0

                with BulkCreateManager(FileKnowledge, chunk_size=1000) as bulk_fk:
                    for fc in c.filechange_set.select_related("file"):
                        if fc.change_type == 'D' or not fc.file.exists:
                            continue
                        sum_file_knowledge_dict[fc.file.id] += (fc.insertions + fc.deletions)
                        k_index = (fc.file_id, author.id)

                        if k_index in file_knowledge_dict:
                            fk = file_knowledge_dict[k_index]
                            fk.added += fc.insertions
                            fk.deleted += fc.deletions
                        else:
                            fk = FileKnowledge(
                                author=author,
                                file=fc.file,
                                added=fc.insertions,
                                deleted=fc.deletions,
                                knowledge=0
                            )
                            file_knowledge_dict[k_index] = fk
                            bulk_fk.add(fk)

                        if fc.file.id in file_owners:
                            file_owner = file_owners[fc.file.id]
                        else:
                            file_owner = author.id
                        if author.id == file_owner:
                            add_self += fc.insertions
                            del_self += fc.deletions
                        else:
                            add_others += fc.insertions
                            del_others += fc.deletions

                        if author.id == file_owner:
                            add_self += fc.insertions
                            del_self += fc.deletions
                        else:
                            add_others += fc.insertions
                            del_others += fc.deletions

                        val = df.at[fc.file.id, author.id]
                        df.at[fc.file.id, author.id] = val + fc.insertions

                        deletions = fc.deletions
                        r = df.loc[fc.file.id]

                        while deletions > 0:
                            imax = r.idxmax(axis=1)
                            v = df.at[fc.file.id, imax]
                            if v >= deletions:
                                df.at[fc.file.id, imax] = v - deletions
                                deletions = 0
                            else:
                                if v <= 0:
                                    break
                                deletions -= v
                                df.at[fc.file.id, imax] = 0

                        imax = r.idxmax(axis=1)
                        if df.at[fc.file.id, imax] > 0:
                            file_owners[fc.file.id] = imax

                cblame = CommitBlame(
                    commit=c,
                    loc=df[author.id].sum(),
                    add_others=add_others,
                    add_self=add_self,
                    del_others=del_others,
                    del_self=del_self,
                    author=author,
                    date=c.date
                )
                bulk.add(cblame)

        logger.info("FILE KNOWLEDGE POST PROCESSING")
        # adjust knowledge factor
        with BulkUpdateManager(FileKnowledge, ['knowledge']) as bulk:
            for fk in file_knowledge_dict.values():
                k_total = sum_file_knowledge_dict[fk.file_id]
                fk.knowledge = min(1.0, (fk.added + fk.deleted) / k_total if k_total else 0.0)
                bulk.add(fk)

        logger.info("FILE OWNERS")
        with BulkUpdateManager(File, ['coupled_files', 'soc'], chunk_size=1000) as bulk:
            for file in self.file_cache.values():
                file.coupled_files = file.count_coupled_files(file.commits)
                file.soc = file.calc_soc(file.commits)
                bulk.add(file)
        logger.info("END FILE OWNERS")

    def process_blames(self, branch: Branch):
        blames = Blame.objects.filter(repository=self.repo, branch=branch)
        total_sum_loc = 0
        locs = defaultdict(int)
        blames_id = dict()
        for blame in blames:
            blames_id[blame.author] = blame.id
            commits = Commit.objects.filter(
                branch=branch,
                repository=self.repo,
                author=blame.author
            ).order_by("date")

            file_blames = FileBlame.objects.filter(author=blame.author, commit__in=commits)
            fd = dict()
            for fb in file_blames:
                if fb.file not in fd:
                    fd[fb.file] = (fb.loc, fb.commit.date)
                else:
                    (loc, date) = fd[fb.file]
                    if date < fb.commit.date:
                        fd[fb.file] = (fb.loc, fb.commit.date)
            sum_loc = sum([loc for (loc, d) in fd.values()])
            total_sum_loc += sum_loc
            locs[blame.author] += sum_loc

        (total_insertions, total_deletions) = calc_total_ins_and_dels(self.repo, branch)
        with BulkUpdateManager(Blame, ["loc", "impact", "log_impact", "ownership", "lines", "insertions", "deletions",
                                       "add_self", "add_others", "del_self", "del_others", "net", "work_self",
                                       "work_others", "raw_throughput", "raw_churn", "net_avg", "churn", "throughput",
                                       "self_churn", "self_throughput", "commits", "changes"]) as bulk:
            for author in locs.keys():
                commits = Commit.objects.filter(
                    branch=branch,
                    repository=self.repo,
                    author=author
                ).order_by("date")
                bulk.add(update_blame_object({"id": blames_id[author], "loc": float(locs[author])}, author, self.repo,
                                             branch, commits, total_sum_loc, total_insertions, total_deletions,
                                             for_bulk=True))

    def __get_or_create_author(self, email, name):
        cache_key = (email, self.owner)
        if cache_key not in self.developer_cache:
            dev, created = Developer.objects.get_or_create(email=email, owner=self.owner, defaults={'name': name})
            self.developer_cache[cache_key] = dev
            dev.repos.add(self.repo)
            return dev
        return self.developer_cache[cache_key]

    def create_commit(self, git_commit, author, branch):
        hexsha = git_commit.hexsha
        date = git_commit.authored_datetime
        msg = git_commit.message
        is_merge = len(git_commit.parents) > 1
        stats = git_commit.stats.total
        ins = int(stats['insertions']) if not is_merge else 0
        dels = int(stats['deletions']) if not is_merge else 0
        lines = int(stats['lines']) if not is_merge else 0
        net = int(ins - dels) if not is_merge else 0
        real_author = author.get_principal()
        return Commit(
            hexsha=hexsha,
            repository=self.repo,
            branch=branch,
            date=make_aware(date) if not is_aware(date) else date,
            message=msg,
            insertions=ins,
            deletions=dels,
            lines=lines,
            net=net,
            is_merge=is_merge,
            author=real_author,
            original_author=author
        )

    def get_file_key(self, filename, branch):
        pkey = str(Path(self.repo.base_directory) / Path(filename))
        return pkey + '@' + branch.name

    def create_file_change_object(self, commit: Commit, file: File, fc, git_commit):
        ins = int(fc['insertions'])
        dels = int(fc['deletions'])
        change_type = self.__det_change_status(git_commit, git_commit.parents)
        return FileChange(
            file=file,
            author=commit.author,
            commit=commit,
            date=commit.date,
            insertions=ins,
            deletions=dels,
            change_type=change_type
        )

    def __det_change_status(self, commit, parents):
        for parent in parents:
            key = (str(commit), str(parent))
            if key in self.dict_change_status:
                return self.dict_change_status[key]
            for change in parent.diff(commit):
                self.dict_change_status[key] = change.change_type
                return change.change_type
        return ""

    def create_file(self, filename, branch):
        pkey = str(Path(self.repo.base_directory) / Path(filename))
        key = pkey + '@' + branch.name
        if key in self.file_cache:
            file = self.file_cache[key]
            return self.file_cache[key], file.id is None

        p = Path(filename)
        parent = p.parent
        name = p.name
        if parent == name:
            parent = ''
        file_path = self.get_or_create_filepath(branch, parent)
        try:
            path = Path(pkey)
            exists = path.is_file()

            if not exists:
                file = self.create_file_object(filename, branch, file_path, name, False)
            else:
                try:
                    analysis = SourceAnalysis.from_file(pkey, self.repo.name)
                    empty = analysis.state == SourceState.empty.name
                    binary = analysis.state == SourceState.binary.name
                    indent_complexity = calculate_complexity_in(pkey) if not empty and not binary else 0
                    is_code = (not binary) and (not empty) and language_is_code(analysis.language)
                    lines = 0
                    if not binary:
                        encoding = detect_encoding(path)
                        with open(path, "r", newline='', encoding=encoding, errors='ignore') as fd:
                            lines = sum(1 for _ in fd)
                    file = File(
                        filename=filename,
                        repository=self.repo,
                        branch=branch,
                        path=file_path,
                        name=name,
                        language=analysis.language,
                        code=analysis.code,
                        doc=analysis.documentation,
                        blanks=analysis.empty,
                        empty=empty,
                        strings=analysis.string,
                        binary=binary,
                        exists=True,
                        is_code=is_code,
                        indent_complexity=indent_complexity,
                        lines=lines
                    )
                except Exception as e:
                    file = self.create_file_object(filename, branch, file_path, name, True)
                    logger.info('error on {}'.format(pkey))
                    tb = traceback.format_exc(e)
                    logger.info(tb)

            self.file_cache[key] = file
        except Exception as e:
            tb = traceback.format_exc(e)
            logger.info(tb)
            file = self.create_file_object(filename, branch, file_path, name, False)
            self.file_cache[key] = file
        return self.file_cache[key], True

    def create_file_object(self, filename, branch, file_path, name, exists):
        return File(
            filename=filename,
            repository=self.repo,
            branch=branch,
            path=file_path,
            name=name,
            language='',
            code=0,
            doc=0,
            blanks=0,
            lines=0,
            empty=True,
            strings=0,
            binary=False,
            exists=exists,
            is_code=False,
            changes=0,
            indent_complexity=0
        )

    def get_or_create_filepath(self, branch: Branch, path):
        pkey = str(Path(self.repo.base_directory) / Path(path))
        cache_key = pkey + '@' + branch.name

        if cache_key not in self.filepath_cache:
            path_obj = Path(path)

            if str(path) != '.' and str(path.parent) != '':
                parent = self.get_or_create_filepath(branch, path_obj.parent)
            else:
                parent = None

            filepath, created = FilePath.objects.get_or_create(
                path=path,
                branch=branch,
                repository=self.repo,
                defaults=dict(
                    name=path_obj.name,
                    exists=Path(pkey).exists(),
                    parent=parent
                )
            )

            self.filepath_cache[cache_key] = filepath

        return self.filepath_cache[cache_key]

    def create_file_blame_object(self, filename, commit: Commit, file: File):
        if not file.exists:
            return None
        blames = self.git_repo.blame(commit.hexsha, filename)
        if not blames:
            return None
        loc = 0
        for b in blames:
            if b[0].author.email == commit.author.email:
                loc = loc + len(b[1])
        return FileBlame(file=file, commit=commit, author=commit.author, loc=loc)

    def __process_files_hotspot_weight(self, branch: Branch):
        max_file_changes = File.objects.filter(repository=self.repo, branch=branch) \
                               .aggregate(max=Max('changes'))['max'] or 1
        File.objects.filter(
            repository=self.repo,
            branch=branch
        ).update(
            hotspot_weight=F('changes') / float(max_file_changes)
        )
