from collections.abc import AsyncIterator, Iterable
from http import HTTPStatus
from typing import Any, Final, Protocol

import httpx

from bot.models import (
    MarketSnapshot,
    Notification,
    SalaryRow,
    Skill,
    Subscription,
    SubscriptionDraft,
    Vacancy,
)

TIMEOUT: Final = httpx.Timeout(10.0, read=60.0)


class ApiError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"API responded with {status_code}: {detail}")
        self.status_code = status_code


class BotApi(Protocol):
    async def register(self, chat_id: int, username: str) -> None: ...
    async def forget(self, chat_id: int) -> None: ...
    async def weekly_report_enabled(self, chat_id: int) -> bool: ...
    async def set_weekly_report(self, chat_id: int, *, enabled: bool) -> None: ...
    async def weekly_report_subscribers(self) -> list[int]: ...
    async def skills(self, *, limit: int) -> list[Skill]: ...
    async def subscriptions(self, chat_id: int) -> list[Subscription]: ...
    async def create_subscription(self, chat_id: int, draft: SubscriptionDraft) -> Subscription: ...
    async def set_subscription_active(
        self, chat_id: int, subscription_id: int, *, active: bool
    ) -> Subscription: ...
    async def delete_subscription(self, chat_id: int, subscription_id: int) -> None: ...
    async def search(self, text: str, *, limit: int) -> list[Vacancy]: ...
    async def market_overview(self) -> list[MarketSnapshot]: ...
    async def salaries(self, language: str, *, group: str) -> list[SalaryRow]: ...
    async def latest_report(self) -> bytes | None: ...
    async def notifications(self, *, limit: int) -> list[Notification]: ...
    async def acknowledge(self, deliveries: Iterable[tuple[int, int]]) -> None: ...


class JobPulseApi:
    def __init__(
        self,
        base_url: str,
        *,
        username: str,
        password: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT, transport=transport)
        self._credentials = {"username": username, "password": password}
        self._access_token: str | None = None

    async def close(self) -> None:
        await self._client.aclose()

    async def register(self, chat_id: int, username: str) -> None:
        await self._request("POST", "subscribers/", json={"chat_id": chat_id, "username": username})

    async def forget(self, chat_id: int) -> None:
        await self._request("DELETE", f"subscribers/{chat_id}/", allow_missing=True)

    async def weekly_report_enabled(self, chat_id: int) -> bool:
        response = await self._request("GET", f"subscribers/{chat_id}/")
        return bool(response.json()["weekly_report"])

    async def set_weekly_report(self, chat_id: int, *, enabled: bool) -> None:
        await self._request("PATCH", f"subscribers/{chat_id}/", json={"weekly_report": enabled})

    async def weekly_report_subscribers(self) -> list[int]:
        pages = self._pages("subscribers/", params={"weekly_report": "true", "page_size": 100})
        return [item["chat_id"] async for item in pages]

    async def skills(self, *, limit: int) -> list[Skill]:
        response = await self._request("GET", "skills/", params={"page_size": limit}, public=True)
        return [Skill.from_json(item) for item in response.json()["results"]]

    async def subscriptions(self, chat_id: int) -> list[Subscription]:
        response = await self._request("GET", f"subscribers/{chat_id}/subscriptions/")
        return [Subscription.from_json(item) for item in response.json()]

    async def create_subscription(self, chat_id: int, draft: SubscriptionDraft) -> Subscription:
        response = await self._request(
            "POST", f"subscribers/{chat_id}/subscriptions/", json=draft.to_json()
        )
        return Subscription.from_json(response.json())

    async def set_subscription_active(
        self, chat_id: int, subscription_id: int, *, active: bool
    ) -> Subscription:
        response = await self._request(
            "PATCH",
            f"subscribers/{chat_id}/subscriptions/{subscription_id}/",
            json={"is_active": active},
        )
        return Subscription.from_json(response.json())

    async def delete_subscription(self, chat_id: int, subscription_id: int) -> None:
        await self._request(
            "DELETE", f"subscribers/{chat_id}/subscriptions/{subscription_id}/", allow_missing=True
        )

    async def search(self, text: str, *, limit: int) -> list[Vacancy]:
        response = await self._request(
            "GET", "vacancies/", params={"q": text, "page_size": limit}, public=True
        )
        return [Vacancy.from_json(item) for item in response.json()["results"]]

    async def market_overview(self) -> list[MarketSnapshot]:
        response = await self._request("GET", "market/overview/", public=True)
        return [MarketSnapshot.from_json(item) for item in response.json()]

    async def salaries(self, language: str, *, group: str) -> list[SalaryRow]:
        response = await self._request(
            "GET",
            "salaries/",
            params={"language": language, "group": group},
            public=True,
            allow_missing=True,
        )
        if response.status_code == HTTPStatus.NOT_FOUND:
            return []
        return [SalaryRow.from_json(item) for item in response.json()]

    async def latest_report(self) -> bytes | None:
        response = await self._request("GET", "reports/latest/", public=True, allow_missing=True)
        return None if response.status_code == HTTPStatus.NOT_FOUND else response.content

    async def notifications(self, *, limit: int) -> list[Notification]:
        response = await self._request("GET", "notifications/", params={"limit": limit})
        return [Notification.from_json(item) for item in response.json()]

    async def acknowledge(self, deliveries: Iterable[tuple[int, int]]) -> None:
        payload = [
            {"subscription": subscription, "vacancy": vacancy}
            for subscription, vacancy in deliveries
        ]
        if payload:
            await self._request("POST", "notifications/", json={"deliveries": payload})

    async def _pages(self, path: str, *, params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        url: str | None = path
        while url is not None:
            response = await self._request("GET", url, params=params if url == path else None)
            payload = response.json()
            for item in payload["results"]:
                yield item
            url = payload["next"]

    async def _request(
        self,
        method: str,
        url: str,
        *,
        public: bool = False,
        allow_missing: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        response = await self._send(method, url, public=public, **kwargs)
        if response.status_code == HTTPStatus.UNAUTHORIZED and not public:
            self._access_token = None
            response = await self._send(method, url, public=public, **kwargs)
        if allow_missing and response.status_code == HTTPStatus.NOT_FOUND:
            return response
        if response.is_error:
            raise ApiError(response.status_code, response.text[:200])
        return response

    async def _send(self, method: str, url: str, *, public: bool, **kwargs: Any) -> httpx.Response:
        headers = {} if public else {"Authorization": f"Bearer {await self._token()}"}
        return await self._client.request(method, url, headers=headers, **kwargs)

    async def _token(self) -> str:
        if self._access_token is None:
            response = await self._client.post("auth/token/", json=self._credentials)
            if response.is_error:
                raise ApiError(response.status_code, "Bot account credentials were rejected")
            self._access_token = str(response.json()["access"])
        return self._access_token
