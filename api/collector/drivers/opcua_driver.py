"""OPC UA driver stub using the asyncua library.

This module provides a basic working skeleton.  Full production features
(subscriptions, certificate handling, monitored items, etc.) are marked
with TODO comments for future implementation.
"""

from __future__ import annotations

from typing import Any

from asyncua import Client as OpcUaClient

from .base import BaseDriver


class OpcUaDriver(BaseDriver):
    """Driver for OPC UA servers (Beckhoff TwinCAT, Siemens, etc.).

    Default NodeID convention used by ME2 TwinCAT projects:
        ``ns=4;s=Application.GVL_ME2.<VarName>``
    """

    def __init__(
        self,
        host: str,
        port: int = 4840,
        name: str = "opcua",
        **kwargs,
    ):
        super().__init__(host=host, port=port, name=name, **kwargs)
        self._endpoint: str = f"opc.tcp://{self.host}:{self.port}"
        self._client: OpcUaClient | None = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Connect to the OPC UA server."""
        self.logger.info("Connecting to OPC UA endpoint %s", self._endpoint)
        try:
            self._client = OpcUaClient(url=self._endpoint)
            # TODO: configure security policy / certificates if required
            # self._client.set_security_string(...)
            await self._client.connect()
            self.logger.info("OPC UA connected to %s", self._endpoint)
            return True
        except Exception:
            self.logger.exception("OPC UA connect exception for %s", self._endpoint)
            self._client = None
            return False

    async def disconnect(self) -> None:
        """Disconnect from the OPC UA server."""
        if self._client is not None:
            self.logger.info("Disconnecting OPC UA %s", self._endpoint)
            try:
                await self._client.disconnect()
            except Exception:
                self.logger.exception("OPC UA disconnect error for %s", self._endpoint)
            finally:
                self._client = None

    async def is_connected(self) -> bool:
        """Check if the OPC UA session is alive.

        A lightweight approach: try to read the server state node.
        """
        if self._client is None:
            return False
        try:
            # Server state node (always present on any OPC UA server)
            node = self._client.get_node("ns=0;i=2259")
            await node.read_value()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def read_variable(self, address: dict) -> Any:
        """Read a variable from the OPC UA server.

        Expected address dict:
            node_id : str   -- Full OPC UA NodeID, e.g.
                               "ns=4;s=Application.GVL_ME2.PartsOK"

        If *node_id* is not provided but *var_name* is, the driver constructs
        the NodeID using the ME2 convention:
            ``ns=4;s=Application.GVL_ME2.<var_name>``
        """
        if self._client is None:
            self.logger.error("OPC UA read called while disconnected")
            return None

        node_id = address.get("node_id")
        if node_id is None:
            var_name = address.get("var_name")
            if var_name is None:
                self.logger.error("OPC UA address must contain 'node_id' or 'var_name'")
                return None
            node_id = f"ns=4;s=Application.GVL_ME2.{var_name}"

        try:
            self.logger.debug("OPC UA reading node_id='%s'", node_id)
            node = self._client.get_node(node_id)
            value = await node.read_value()
            self.logger.debug("OPC UA node_id='%s' value=%s", node_id, value)
            return value
        except Exception:
            self.logger.exception("OPC UA read error node_id='%s' on %s", node_id, self._endpoint)
            return None

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def write_variable(self, address: dict, value: Any) -> bool:
        """Write a value to an OPC UA node.

        Same address convention as read_variable.

        TODO: Handle DataValue / Variant type wrapping for stricter servers.
        """
        if self._client is None:
            self.logger.error("OPC UA write called while disconnected")
            return False

        node_id = address.get("node_id")
        if node_id is None:
            var_name = address.get("var_name")
            if var_name is None:
                self.logger.error("OPC UA address must contain 'node_id' or 'var_name'")
                return False
            node_id = f"ns=4;s=Application.GVL_ME2.{var_name}"

        try:
            self.logger.debug("OPC UA writing node_id='%s' value=%s", node_id, value)
            node = self._client.get_node(node_id)
            await node.write_value(value)
            self.logger.info("OPC UA write OK node_id='%s' value=%s", node_id, value)
            return True
        except Exception:
            self.logger.exception(
                "OPC UA write error node_id='%s' on %s", node_id, self._endpoint
            )
            return False

    # ------------------------------------------------------------------
    # TODO: Subscriptions & Monitored Items
    # ------------------------------------------------------------------
    # async def subscribe(self, node_ids: list[str], handler) -> None:
    #     """Subscribe to data-change notifications for a list of nodes."""
    #     ...
    #
    # async def unsubscribe_all(self) -> None:
    #     """Remove all active subscriptions."""
    #     ...
