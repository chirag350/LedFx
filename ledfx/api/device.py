import logging
from json import JSONDecodeError

import voluptuous
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class DeviceEndpoint(RestEndpoint):
    """REST end-point for querying and managing devices"""

    ENDPOINT_PATH = "/api/devices/{device_id}"

    async def get(self, device_id) -> web.Response:
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        response = device.config
        return web.json_response(data=response, status=200)

    async def put(self, device_id, request) -> web.Response:
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)
        device_config = data.get("config")
        if device_config is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "config" was not provided',
            }
            return web.json_response(data=response, status=400)

        _LOGGER.info(
            ("Updating device {} with config {}").format(
                device_id, device_config
            )
        )

        try:
            device.update_config(device_config)
            response = {"status": "success"}
            status = 200
        except (voluptuous.Error, ValueError) as msg:
            response = {
                "status": "failed",
                "payload": {"type": "warning", "reason": str(msg)},
            }
            status = 202
            # If there's an error updating config, don't write that config, just return an error
            return web.json_response(data=response, status=status)

        # Update and save the configuration
        for device in self._ledfx.config["devices"]:
            if device["id"] == device_id:
                device["config"] = device_config
                break
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        return web.json_response(data=response, status=status)

    async def delete(self, device_id) -> web.Response:
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        device.clear_effect()
        self._ledfx.devices.destroy(device_id)

        # Update and save the configuration
        self._ledfx.config["devices"] = [
            device
            for device in self._ledfx.config["devices"]
            if device["id"] != device_id
        ]
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success"}
        return web.json_response(data=response, status=200)
