import traceback
from collections import defaultdict
from pathlib import Path
import pandas as pd
import pygount
from django.utils.timezone import make_aware, is_aware
from pygount.analysis import SourceState

from analytics.blames import update_blame_object, calc_total_ins_and_dels
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
        self.repo : Repository = repo
        self.owner : User = repo.owner
        self.files_bag = dict()
        self.file_cache = dict()
        self.filepath_cache = dict()
        self.git_repo = GitRepository(self.repo.base_directory)
        self.developer_cache = dict()
        self.commit_cache = dict()
        self.blames_cache = dict()

        self.files_adds = dict()

        rbts = self.repo.branches_to_track.strip()
        if rbts == '':
            self.remote_branches_to_track = [self.repo.default_branch if self.repo.default_branch else 'master']
        else:
            self.remote_branches_to_track = rbts.replace(';', ',').replace(' ', ',').split(',')

        self.current_branch = self.repo.default_branch

    def process(self):
        self.repo.status = Repository.Status.ANALYZING
        self.repo.save()
        self.developer_cache = dict()
        for branch in self.remote_branches_to_track:
            if self.repo.default_branch == '':
                self.repo.default_branch = branch
                self.repo.save()

            self.__process_branch(branch)

        if self.repo.default_branch > '':
            self.git_repo.checkout(self.repo.default_branch)

    def __process_branch(self, branch_name: str):
        logger.info("CHECKOUT BRANCH {}".format(branch_name))
        if not self.git_repo.checkout(branch_name):
            return None

        branch, created = Branch.objects.get_or_create(name=branch_name, repository=self.repo)
        logger.info('BRANCH %s CREATED: %s', branch_name, created)

        self.__process_commits(branch)
        self.__process_fileknowledge(branch)
        self.__process_blames(branch)
        return branch

    def __process_commits(self, branch: Branch):
        commit_history = self.git_repo.get_commits(branch=branch.name)

        logger.info('BEGIN COMMIT HISTORY')
        for commit in commit_history:
            author_email = commit.author.email
            author = self.__get_author(author_email, commit.author.name)
            self.__process_commit(commit, author, branch)
        logger.info("END COMMIT HISTORY")

    def __process_fileknowledge(self, branch: Branch):
        index = list(File.objects.filter(repository=self.repo, branch=branch).values_list('id', flat=True))
        authors_id = set(Commit.objects.order_by('author').values_list('author', flat=True).distinct())
        df = pd.DataFrame(0, index=index, columns=authors_id)

        file_knowledge_dict = dict()
        sum_file_knowledge_dict = defaultdict(int)

        file_owners = dict()
        for c in Commit.objects.filter(branch=branch, repository=self.repo).select_related("author").order_by("date"):
            if c.is_merge:
                continue
            author = c.author

            add_others = 0
            add_self = 0
            del_self = 0
            del_others = 0

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
                    fk, created = FileKnowledge.objects.get_or_create(
                        author=author,
                        file=fc.file,
                        defaults=dict(
                            added=fc.insertions,
                            deleted=fc.deletions,
                            knowledge=0
                        )
                    )
                    file_knowledge_dict[k_index] = fk

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

            CommitBlame.objects.get_or_create(
                commit=c,
                defaults=dict(
                    loc=df[author.id].sum(),
                    add_others=add_others,
                    add_self=add_self,
                    del_others=del_others,
                    del_self=del_self,
                    author=author,
                    date=c.date
                )
            )

        logger.info("FILE KNOWLEDGE POST PROCESSING")
        # adjust knowledge factor
        for fk in file_knowledge_dict.values():
            k_total = sum_file_knowledge_dict[fk.file_id]
            fk.knowledge = min(1.0, (fk.added + fk.deleted) / k_total if k_total else 0.0)
            fk.save()

        logger.info("FILE OWNERS")
        for file in File.objects.filter(repository=self.repo, branch=branch):
            file.coupled_files = file.calc_temporal_coupling(file.commits)
            file.soc = file.calc_soc(file.commits)

            if file.id in file_owners:
                knowledge_owner_id = file_owners[file.id]
                try:
                    file.knowledge_owner = Developer.objects.get(pk=knowledge_owner_id)
                except Developer.DoesNotExist:
                    pass

            file.save()

    def __process_blames(self, branch: Branch):
        locs = dict()
        total_sum_loc = 0
        for author in self.developer_cache.values():
            commits = Commit.objects.filter(
                branch=branch,
                repository=self.repo,
                author=author
            ).order_by("date")

            file_blames = FileBlame.objects.filter(author=author, commit__in=commits)
            fd = dict()
            for fb in file_blames:
                if not fb.file in fd:
                    fd[fb.file] = (fb.loc, fb.commit.date)
                else:
                    (loc, date) = fd[fb.file]
                    if date < fb.commit.date:
                        fd[fb.file] = (fb.loc, fb.commit.date)
            sum_loc = sum([loc for (loc, d) in fd.values()])
            locs[author] = sum_loc
            total_sum_loc += sum_loc

        (total_insertions, total_deletions) = calc_total_ins_and_dels(self.repo, branch)
        for author in locs.keys():
            commits = Commit.objects.filter(
                branch=branch,
                repository=self.repo,
                author=author
            ).order_by("date")
            update_blame_object({"loc":float(locs[author])},
                                author, self.repo, branch, commits, total_sum_loc, total_insertions, total_deletions)

    def __get_author(self, email, name):
        cache_key = (email, self.owner)
        if cache_key not in self.developer_cache:
            dev, created = Developer.objects.get_or_create(email=email, owner=self.owner, defaults={'name': name})
            self.developer_cache[cache_key] = dev
            dev.repos.add(self.repo)
            return dev
        return self.developer_cache[cache_key]

    def __process_commit(self, git_commit, author, branch):
        hexsha = str(git_commit.hexsha)
        date = git_commit.authored_datetime

        cache_key = (hexsha, date)
        if cache_key not in self.commit_cache:
            msg = git_commit.message
            is_merge = len(git_commit.parents) > 1
            stats = git_commit.stats.total
            ins = int(stats['insertions']) if not is_merge else 0
            dels = int(stats['deletions']) if not is_merge else 0
            lines = int(stats['lines']) if not is_merge else 0
            net = int(ins - dels) if not is_merge else 0
            real_author = author.get_principal()

            commit, created = Commit.objects.get_or_create(
                hexsha=hexsha,
                repository=self.repo,
                branch=branch,
                defaults=dict(
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
            )

            self.commit_cache[cache_key] = commit

            self.__process_files(commit, branch, git_commit.stats.files, git_commit)

        return self.commit_cache[cache_key]

    def __process_files(self, commit, branch, files, git_commit):
        ct = dict()
        for parent in git_commit.parents:
            for change in parent.diff(git_commit):
                ct[change.a_blob.path if change.a_blob else change.b_blob.path] = change.change_type

        for fn in files.keys():
            file = self.__process_file(fn, branch)
            fc, created = self.__process_file_change(commit, file, files[fn], ct[fn] if fn in ct else '')

            if file.exists and fc.change_type in ['A','M'] or fc.change_type == '':
                self.__process_file_blame(fn, commit, file)

    def __process_file_change(self, commit:Commit, file: File, fc, change_type):
        ins = int(fc['insertions'])
        dels = int(fc['deletions'])
        return FileChange.objects.get_or_create(
            file=file,
            commit=commit,
            defaults=dict(
                repository=commit.repository,
                branch=commit.branch,
                insertions=ins,
                deletions=dels,
                change_type=change_type
            )
        )

    def __process_file(self, filename, branch):
        pkey = str(Path(self.repo.base_directory) / Path(filename))
        key = pkey + '@' + branch.name
        if key in self.file_cache:
            return self.file_cache[key]

        p = Path(filename)
        parent = p.parent
        name = p.name
        if parent == name:
            parent = ''
        file_path = self.__get_filepath(branch, parent)
        try:
            path = Path(pkey)
            exists = path.is_file()
            if exists:
                analysis = None
                try:
                    analysis = pygount.source_analysis(pkey, self.repo.name)
                except Exception as e:
                    logger.info('error on {}'.format(pkey))
                    tb = traceback.format_exc(e)
                    logger.info(tb)

                empty = analysis.state == SourceState.empty.name
                binary = analysis.state == SourceState.binary.name
                indent_complexity = calculate_complexity_in(pkey) if not empty and not binary else 0
                is_code = (not binary) and (not empty) and language_is_code(analysis.language)
                lines = 0
                if not binary:
                    encoding = detect_encoding(path)
                    with open(path, "r", newline='', encoding=encoding, errors='ignore') as fd:
                        lines = sum(1 for _ in fd)

                file, created = File.objects.get_or_create(
                    filename=filename,
                    repository=self.repo,
                    branch=branch,
                    defaults=dict(
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
                )
                self.file_cache[key] = file
            else:
                file, created = self.__get_or_create_file(filename, branch, file_path, name)
                self.file_cache[key] = file
        except Exception as e:
            tb = traceback.format_exc(e)
            logger.info(tb)
            file, created = self.__get_or_create_file(filename, branch, file_path, name)
            self.file_cache[key] = file

        return self.file_cache[key]

    def __get_or_create_file(self, filename, branch, file_path, name):
        return File.objects.get_or_create(
            filename=filename,
            repository=self.repo,
            branch=branch,
            defaults=dict(
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
                exists=False,
                is_code=False,
                indent_complexity=0
            )
        )

    def __get_filepath(self, branch: Branch, path):
        pkey = str(Path(self.repo.base_directory) / Path(path))
        cache_key = pkey + '@' + branch.name

        if cache_key not in self.filepath_cache:
            path_obj = Path(path)

            if str(path) != '.' and str(path.parent) != '':
                parent = self.__get_filepath(branch, path_obj.parent)
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

    def __process_file_blame(self, filename, commit: Commit, file: File):
        if not file.exists:
            return None
        blames = self.git_repo.blame(commit.hexsha, filename)
        if not blames:
            return None
        loc = 0
        for b in blames:
            if b[0].author.email == commit.author.email:
                loc = loc + len(b[1])
        blame, created = FileBlame.objects.get_or_create(file=file, commit=commit, author=commit.author, loc=loc)
        return blame

