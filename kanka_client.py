"""
Minimal Kanka CE REST API client.
Covers the entity types needed for campaign world-building.

Usage:
    python kanka_client.py

Requires:
    pip install requests
"""

import json
import os
import requests

KANKA_BASE_URL = os.environ.get("KANKA_BASE_URL", "http://localhost:8081")
KANKA_TOKEN = os.environ.get("KANKA_TOKEN", "")
API_BASE = f"{KANKA_BASE_URL}/api/1.0"


class KankaClient:
    def __init__(self, token: str, base_url: str = KANKA_BASE_URL):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        self.base = f"{base_url}/api/1.0"

    def _get(self, path: str) -> dict:
        r = self.session.get(f"{self.base}{path}")
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, data: dict) -> dict:
        r = self.session.post(f"{self.base}{path}", json=data)
        r.raise_for_status()
        return r.json()

    def _patch(self, path: str, data: dict) -> dict:
        r = self.session.patch(f"{self.base}{path}", json=data)
        r.raise_for_status()
        return r.json()

    def _delete(self, path: str) -> None:
        r = self.session.delete(f"{self.base}{path}")
        r.raise_for_status()

    # ── Campaigns ────────────────────────────────────────────────────────────

    def list_campaigns(self) -> list:
        return self._get("/campaigns")["data"]

    def create_campaign(self, name: str, locale: str = "en") -> dict:
        return self._post("/campaigns", {"name": name, "locale": locale})["data"]

    # ── Locations ─────────────────────────────────────────────────────────────

    def list_locations(self, campaign_id: int) -> list:
        return self._get(f"/campaigns/{campaign_id}/locations")["data"]

    def create_location(self, campaign_id: int, name: str, **kwargs) -> dict:
        return self._post(f"/campaigns/{campaign_id}/locations", {"name": name, **kwargs})["data"]

    def get_location(self, campaign_id: int, location_id: int) -> dict:
        return self._get(f"/campaigns/{campaign_id}/locations/{location_id}")["data"]

    # ── Characters ────────────────────────────────────────────────────────────

    def list_characters(self, campaign_id: int) -> list:
        return self._get(f"/campaigns/{campaign_id}/characters")["data"]

    def create_character(self, campaign_id: int, name: str, **kwargs) -> dict:
        return self._post(f"/campaigns/{campaign_id}/characters", {"name": name, **kwargs})["data"]

    # ── Organisations ─────────────────────────────────────────────────────────

    def list_organisations(self, campaign_id: int) -> list:
        return self._get(f"/campaigns/{campaign_id}/organisations")["data"]

    def create_organisation(self, campaign_id: int, name: str, **kwargs) -> dict:
        return self._post(f"/campaigns/{campaign_id}/organisations", {"name": name, **kwargs})["data"]

    # ── Events ────────────────────────────────────────────────────────────────

    def create_event(self, campaign_id: int, name: str, **kwargs) -> dict:
        return self._post(f"/campaigns/{campaign_id}/events", {"name": name, **kwargs})["data"]

    # ── Notes ─────────────────────────────────────────────────────────────────

    def create_note(self, campaign_id: int, name: str, **kwargs) -> dict:
        return self._post(f"/campaigns/{campaign_id}/notes", {"name": name, **kwargs})["data"]

    # ── Tags ──────────────────────────────────────────────────────────────────

    def create_tag(self, campaign_id: int, name: str, **kwargs) -> dict:
        return self._post(f"/campaigns/{campaign_id}/tags", {"name": name, **kwargs})["data"]

    # ── Generic entity attributes ─────────────────────────────────────────────

    def set_attributes(self, campaign_id: int, entity_id: int, attributes: list) -> dict:
        """
        attributes: [{"name": "Key", "value": "Val", "type": 0}, ...]
        type: 0=text, 1=list, 2=block, 3=checkbox, 4=section, 5=random_value
        """
        return self._post(f"/campaigns/{campaign_id}/entities/{entity_id}/attributes", attributes)


def demo(token: str):
    client = KankaClient(token)

    print("Listing campaigns...")
    campaigns = client.list_campaigns()
    print(f"  Found {len(campaigns)} campaign(s)")

    if not campaigns:
        print("Creating test campaign...")
        campaign = client.create_campaign("Demo World")
        print(f"  Created: {campaign['name']} (id={campaign['id']})")
    else:
        campaign = campaigns[0]
        print(f"  Using: {campaign['name']} (id={campaign['id']})")

    cid = campaign["id"]

    print(f"\nCreating location in campaign {cid}...")
    loc = client.create_location(
        cid,
        name="The Wandering Market",
        type="Settlement",
        entry="A sprawling bazaar that appears in different cities each week, guided by an unknown force.",
    )
    print(f"  Created location: {loc['name']} (id={loc['id']}, entity_id={loc['entity_id']})")

    print(f"\nCreating character in campaign {cid}...")
    char = client.create_character(
        cid,
        name="Sera Voss",
        title="Spymaster of the Fourth Circle",
        entry="Operates from the shadows of the capital.",
    )
    print(f"  Created character: {char['name']} (id={char['id']})")

    print(f"\nCreating organisation in campaign {cid}...")
    org = client.create_organisation(
        cid,
        name="The Fourth Circle",
        type="Secret Society",
        entry="An intelligence network spanning three kingdoms.",
    )
    print(f"  Created organisation: {org['name']} (id={org['id']})")

    print("\nDone. Kanka CE REST API is fully operational.")


if __name__ == "__main__":
    token = os.environ.get("KANKA_TOKEN")
    if not token:
        print("Set KANKA_TOKEN env var to your API token")
        raise SystemExit(1)
    demo(token)
