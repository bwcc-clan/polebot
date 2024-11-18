
import asyncio
from typing import Optional

from .crcon_server_details import CRCONServerDetails
from .models import VoteMapUserConfig


class VotemapManager:
    def __init__(self, server_details: CRCONServerDetails) -> None:
        self.server_details = server_details
        self.stop_event = asyncio.Event()
        self.votemap_config: Optional[VoteMapUserConfig] = None

    async def run(self) -> None:
        await self.stop_event.wait()

    def stop(self) -> None:
        self.stop_event.set()

    async def _read_settings(self) -> None:
        pass
