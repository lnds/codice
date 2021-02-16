import traceback
from collections import defaultdict
from pathlib import Path

import pandas as pd
from pygount import SourceAnalysis
from django.db.models import Max, F
from django.utils.timezone import make_aware, is_aware
from pygount.analysis import SourceState

from analytics.blames import calc_total_blame, update_blame_object
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


class RepoAnalyzer(object):

    def __init__(self, repo: Repository):
        self.repo: Repository = repo
        self.owner: User = repo.owner
        self.filepath_cache = dict()
        self.file_cache = dict()
        self.git_repo = GitRepository(self.repo.base_directory)
        self.developer_cache = dict()

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

        self.create_commits(branch)
        self.__process_files_hotspot_weight(branch)
        blames_created = []
        for author in self.developer_cache.values():
            blames_created.append(Blame(author=author, repository=self.repo, branch=branch, loc=0))
        Blame.objects.bulk_create(blames_created)
        self.process_fileknowledge(branch)
        self.process_blames(branch)
        return branch

    def create_commits(self, branch: Branch):
        commit_history = self.git_repo.get_commits(branch=branch.name)

        logger.info('BEGIN COMMIT HISTORY')
        bulk = []
        commit_dict = {}
        for commit in commit_history:
            author_email = commit.author.email
            author = self.__get_or_create_author(author_email, commit.author.name)
            c = self.create_commit(commit, author, branch)
            bulk.append(c)
            commit_dict[commit] = c
            if len(bulk) == 100:
                Commit.objects.bulk_create(bulk)
                for (git_commit, c) in commit_dict.items():
                    self.create_files(c, branch, git_commit.stats.files, git_commit)
                bulk = []
                commit_dict = {}

        Commit.objects.bulk_create(bulk)
        for (git_commit, commit) in commit_dict.items():
            self.create_files(commit, branch, git_commit.stats.files, git_commit)

        logger.info("END COMMIT HISTORY")

    def process_fileknowledge(self, branch: Branch):
        logger.info("FILE KNOWLEDGE PROCESSING")

        index = list(File.objects.filter(repository=self.repo, branch=branch).values_list('id', flat=True))
        authors_id = set(Commit.objects.order_by('author').values_list('author', flat=True).distinct())
        df = pd.DataFrame(0, index=index, columns=authors_id)

        file_knowledge_dict = dict()
        sum_file_knowledge_dict = defaultdict(int)

        file_owners = dict()
        bulk = []
        for c in Commit.objects.filter(branch=branch, repository=self.repo).select_related("author").order_by("date"):
            if c.is_merge:
                continue
            author = c.author

            add_others = 0
            add_self = 0
            del_self = 0
            del_others = 0

            bulk_fk = []
            for fc in c.filechange_set.select_related("file").all():
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
                    bulk_fk.append(fk)

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

                if len(bulk_fk) == 100:
                    FileKnowledge.objects.bulk_create(bulk_fk)
                    bulk_fk  = []

            FileKnowledge.objects.bulk_create(bulk_fk)
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
            bulk.append(cblame)
            if len(bulk) == 200:
                CommitBlame.objects.bulk_create(bulk)
                bulk = []

        CommitBlame.objects.bulk_create(bulk)

        logger.info("FILE KNOWLEDGE POST PROCESSING")
        # adjust knowledge factor
        bulk = []
        for fk in file_knowledge_dict.values():
            k_total = sum_file_knowledge_dict[fk.file_id]
            fk.knowledge = min(1.0, (fk.added + fk.deleted) / k_total if k_total else 0.0)
            bulk.append(fk)
        FileKnowledge.objects.bulk_update(bulk, ['knowledge'])

        logger.info("FILE OWNERS")
        bulk = []
        for file in self.file_cache.values():
            file.coupled_files = file.calc_temporal_coupling(file.commits)
            file.soc = file.calc_soc(file.commits)

            bulk.append(file)
            if len(bulk) == 250:
                File.objects.bulk_update(bulk, ['coupled_files', 'soc'])
                bulk = []

        File.objects.bulk_update(bulk, ['coupled_files', 'soc'])
        logger.info("END FILE OWNERS")

    def process_blames(self, branch: Branch):
        blames = Blame.objects.filter(repository=self.repo, branch=branch)
        bulk = []
        for blame in blames:
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
            blame.loc = sum([loc for (loc, d) in fd.values()])
            bulk.append(blame)
            if len(bulk) == 250:
                FileBlame.objects.bulk_update(bulk, ['loc'])
                bulk = []

        FileBlame.objects.bulk_update(bulk, ['loc'])

        (total_blame, total_insertions, total_deletions) = calc_total_blame(self.repo, branch)
        for blame in blames:
            commits = Commit.objects.filter(
                branch=branch,
                repository=self.repo,
                author=blame.author
            ).order_by("date")
            update_blame_object(blame, blame.author, commits, total_blame, total_insertions, total_deletions)

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

    def create_files(self, commit, branch, files, git_commit):
        created_files = []
        updated_files = []
        for fn in files.keys():
            file, created = self.create_file(fn, branch)
            file.changes += 1
            if created:
                created_files.append(file)
            else:
                updated_files.append(file)

        File.objects.bulk_create(created_files)
        File.objects.bulk_update(updated_files, ['changes'])

        created_fcs = []
        for f in updated_files:
            self.file_cache[self.get_file_key(f.filename, branch)] = f

        created_file_blames = []
        for f in created_files:
            self.file_cache[self.get_file_key(f.filename, branch)] = f
            fn = f.filename
            fc = self.create_file_change_object(commit, f, files[fn], git_commit)
            created_fcs.append(fc)
            if f.exists and fc.change_type in ['A', 'M'] or fc.change_type == '':
                blame = self.create_file_blame_object(fn, commit, f)
                if blame:
                    created_file_blames.append(blame)
        FileChange.objects.bulk_create(created_fcs)
        FileBlame.objects.bulk_create(created_file_blames)

    def get_file_key(self, filename, branch):
        pkey = str(Path(self.repo.base_directory) / Path(filename))
        return pkey + '@' + branch.name

    def create_file_change_object(self, commit: Commit, file: File, fc, git_commit):
        ins = int(fc['insertions'])
        dels = int(fc['deletions'])
        change_type = self.__det_change_status(git_commit, git_commit.parents)
        return FileChange(
            file=file,
            commit=commit,
            repository=commit.repository,
            branch=commit.branch,
            insertions=ins,
            deletions=dels,
            change_type=change_type
        )

    @staticmethod
    def __det_change_status(commit, parents):
        for parent in parents:
            for change in parent.diff(commit):
                return change.change_type
        return ""

    def create_file(self, filename, branch):
        pkey = str(Path(self.repo.base_directory) / Path(filename))
        key = pkey + '@' + branch.name
        created = False
        if key in self.file_cache:
            return self.file_cache[key], created

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
