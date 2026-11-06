"""The two Hugging Face calls the weekly refresh makes: read the dataset's state, and publish one commit.

Kept separate so the tests can swap in a fake with the same two methods.
"""
import os

REPO_ID = os.environ.get("CBA_HF_REPO", "abigailhaddad/opm-cba-agreements")


class HfClient:
    def __init__(self, repo_id=REPO_ID, token=None):
        self.repo_id = repo_id
        self.token = token or os.environ.get("HF_TOKEN") or None

    def read_state(self):
        """Return (revision, set of file paths, bytes of agreements.csv or None). Works without a token."""
        from huggingface_hub import HfApi, hf_hub_download
        from huggingface_hub.errors import EntryNotFoundError, RepositoryNotFoundError
        api = HfApi(token=self.token)
        try:
            info = api.dataset_info(self.repo_id)
        except RepositoryNotFoundError:
            return None, set(), None
        revision = info.sha
        files = set(api.list_repo_files(self.repo_id, repo_type="dataset", revision=revision))
        try:
            path = hf_hub_download(self.repo_id, "agreements.csv", repo_type="dataset", revision=revision,
                                   token=self.token)
            csv_bytes = open(path, "rb").read()
        except EntryNotFoundError:
            csv_bytes = None
        return revision, files, csv_bytes

    def commit(self, ops, message, parent_commit):
        """One commit that only adds or overwrites files. Fails if the dataset changed since parent_commit."""
        from huggingface_hub import CommitOperationAdd, HfApi
        api = HfApi(token=self.token)
        operations = [CommitOperationAdd(path_in_repo=repo_path, path_or_fileobj=local) for repo_path, local in ops]
        assert all(isinstance(o, CommitOperationAdd) for o in operations), "only additions are allowed"
        return api.create_commit(repo_id=self.repo_id, repo_type="dataset", operations=operations,
                                 commit_message=message, parent_commit=parent_commit)
