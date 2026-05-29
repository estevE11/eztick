import httpx
from urllib.parse import urlencode

BASE_URL = "https://api.ticktick.com"
AUTH_URL = "https://ticktick.com/oauth/authorize"
TOKEN_URL = "https://ticktick.com/oauth/token"

SCOPES = "tasks:read tasks:write"


class TickTickError(Exception):
    pass


class TickTickClient:
    def __init__(self):
        self._http = httpx.Client(base_url=BASE_URL, timeout=30)
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = None
        self.access_token = None
        self.refresh_token = None

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.access_token:
            h["Authorization"] = f"Bearer {self.access_token}"
        return h

    def setup_app(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def get_authorize_url(self) -> str:
        params = {
            "client_id": self.client_id,
            "scope": SCOPES,
            "state": "eztick",
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict:
        resp = self._http.post(
            TOKEN_URL,
            data={
                "code": code,
                "grant_type": "authorization_code",
                "scope": SCOPES,
                "redirect_uri": self.redirect_uri,
            },
            auth=(self.client_id, self.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise TickTickError(
                f"Token exchange failed ({resp.status_code}): {resp.text}"
            )
        data = resp.json()
        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token")
        return data

    def refresh_access_token(self) -> dict:
        if not self.refresh_token:
            raise TickTickError("No refresh token available")
        resp = self._http.post(
            TOKEN_URL,
            data={
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
                "scope": SCOPES,
            },
            auth=(self.client_id, self.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise TickTickError(
                f"Token refresh failed ({resp.status_code}): {resp.text}"
            )
        data = resp.json()
        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token", self.refresh_token)
        return data

    def _request(self, method: str, path: str, **kwargs):
        resp = self._http.request(method, path, headers=self._headers(), **kwargs)
        if resp.status_code == 401 and self.refresh_token:
            self.refresh_access_token()
            resp = self._http.request(method, path, headers=self._headers(), **kwargs)
        return resp

    def verify_token(self) -> bool:
        resp = self._request("GET", "/open/v1/project")
        return resp.status_code == 200

    def get_projects(self) -> list:
        resp = self._request("GET", "/open/v1/project")
        if resp.status_code != 200:
            raise TickTickError(f"Failed to get projects ({resp.status_code})")
        return resp.json()

    def get_inbox_id(self) -> str:
        projects = self.get_projects()
        for p in projects:
            if p.get("name") == "Inbox":
                return p["id"]
        return "inbox"

    def get_inbox_tasks(self) -> list:
        inbox_id = self.get_inbox_id()
        resp = self._request("GET", f"/open/v1/project/{inbox_id}/data")
        if resp.status_code != 200:
            raise TickTickError(f"Failed to get tasks ({resp.status_code})")
        data = resp.json()
        return data.get("tasks", [])

    def create_task(self, title: str, due_date: str = None) -> dict:
        task = {"title": title, "projectId": "inbox"}
        if due_date:
            task["dueDate"] = due_date
            task["isAllDay"] = True
        resp = self._request("POST", "/open/v1/task", json=task)
        if resp.status_code != 200:
            raise TickTickError(
                f"Failed to create task ({resp.status_code}): {resp.text}"
            )
        return resp.json()

    def complete_task(self, project_id: str, task_id: str, task_data: dict | None = None) -> dict:
        resp = self._request(
            "POST",
            f"/open/v1/project/{project_id}/task/{task_id}/complete",
        )
        if resp.status_code not in (200, 204):
            raise TickTickError(f"Failed to complete task ({resp.status_code})")
        return {}

    def uncomplete_task(self, project_id: str, task_id: str) -> dict:
        resp = self._request(
            "POST",
            f"/open/v1/task/{task_id}",
            json={"id": task_id, "projectId": project_id, "status": 0},
        )
        if resp.status_code != 200:
            raise TickTickError(f"Failed to uncomplete task ({resp.status_code})")
        return resp.json()

    def delete_task(self, project_id: str, task_id: str) -> None:
        resp = self._request(
            "DELETE",
            f"/open/v1/project/{project_id}/task/{task_id}",
        )
        if resp.status_code not in (200, 204):
            raise TickTickError(f"Failed to delete task ({resp.status_code})")

    def update_task(
        self, project_id: str, task_id: str, task_data: dict, title: str, due_date: str = None
    ) -> dict:
        task = dict(task_data)
        task["title"] = title
        if due_date:
            task["dueDate"] = due_date
            task["isAllDay"] = True
        else:
            task.pop("dueDate", None)
            task.pop("isAllDay", None)
        resp = self._request(
            "POST",
            f"/open/v1/task/{task_id}",
            json=task,
        )
        if resp.status_code != 200:
            raise TickTickError(
                f"Failed to update task ({resp.status_code}): {resp.text}"
            )
        return resp.json()
