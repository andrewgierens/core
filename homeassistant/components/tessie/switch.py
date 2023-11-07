"""Switch for performing actions against Tesla."""

from collections.abc import Callable, Coroutine
from typing import Any

from aiohttp import ClientSession
from tessie_api import start_charging, stop_charging

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ACCESS_TOKEN, DOMAIN, MANUFACTURER, TessieDataUpdateCoordinator


def traverse_nested_dict(data_dict, key_path):
    """Get a value by a dot notation."""

    keys = key_path.split(".")
    value = data_dict
    for key in keys:
        value = value.get(key)
        if value is None:
            return None
    return value


def set_nested_dict_value(data_dict, key_path, value):
    """Set a value in a nested dictionary using a dot notation key path."""

    keys = key_path.split(".")
    for key in keys[:-1]:  # Go until the second last key
        data_dict = data_dict.setdefault(
            key, {}
        )  # Get the dict, or create an empty one if the key doesn't exist
    data_dict[keys[-1]] = value  # Set the value for the last key


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the switches for the Ring devices."""
    coordinator: TessieDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    cars = coordinator.data["results"]
    session = async_get_clientsession(hass)

    switches = [
        TessieSwitch(
            coordinator,
            session,
            description,
            config_entry.data[ACCESS_TOKEN],
            car["last_state"]["display_name"],
            car["last_state"]["vehicle_config"]["car_type"],
            car["vin"],
        )
        for description in SENSOR_INFO_TYPES_TESLA
        for car in cars
    ]

    async_add_entities(switches)


class TessieSwitchEntityDescription(SwitchEntityDescription):
    """A class that describes switch entities."""

    def __init__(
        self,
        key: str,
        device_class: SwitchDeviceClass | None = None,
        entity_category: EntityCategory | None = None,
        entity_registry_enabled_default: bool = True,
        entity_registry_visible_default: bool = True,
        force_update: bool = False,
        icon: str | None = None,
        has_entity_name: bool = False,
        name: str | UndefinedType | None = UNDEFINED,
        translation_key: str | None = None,
        unit_of_measurement: str | None = None,
        switchName: str | None = None,
        enabled_func: Callable[[ClientSession, str, str], Coroutine[Any, Any, None]]
        | None = None,
        enabled_value: str | None = None,
        disabled_func: Callable[[ClientSession, str, str], Coroutine[Any, Any, None]]
        | None = None,
        disabled_value: str | None = None,
    ) -> None:
        """Init for Tesla switch."""

        super().__init__(
            key,
            device_class,
            entity_category,
            entity_registry_enabled_default,
            entity_registry_visible_default,
            force_update,
            icon,
            has_entity_name,
            name,
            translation_key,
            unit_of_measurement,
        )
        self.name = switchName
        self.enabled_func = enabled_func
        self.enabled_value = enabled_value
        self.disabled_func = disabled_func
        self.disabled_value = disabled_value

    enabled_func: Callable[
        [ClientSession, str, str], Coroutine[Any, Any, None]
    ] | None = None
    enabled_value: str | None = None
    disabled_func: Callable[
        [ClientSession, str, str], Coroutine[Any, Any, None]
    ] | None = None
    disabled_value: str | None = None


class TessieSwitch(CoordinatorEntity, SwitchEntity):
    """A class for the actual switch."""

    def __init__(
        self,
        coordinator,
        session: ClientSession,
        description: TessieSwitchEntityDescription,
        apiKey: str,
        name: str,
        model: str,
        vin: str,
    ) -> None:
        """Init the switch."""

        super().__init__(coordinator)
        self._description = description
        self._session = session
        self._apiKey = apiKey
        self._name = name
        self._model = model
        self._vin = vin
        self._is_charging = False

    def getCarByVin(self, vin: str) -> Any:
        """Retrieve the inverter by name."""

        for car in self.coordinator.data["results"]:
            if car["vin"] == vin:
                return car
        return None

    @property
    def name(self) -> str:
        """Set the name of the switch."""
        return str(self._description.name)

    @property
    def device_info(self) -> DeviceInfo:
        """Set the device info for the switch."""
        return DeviceInfo(
            identifiers={(DOMAIN, MANUFACTURER)},
            name=self._name,
            manufacturer=MANUFACTURER,
            model=self._model,
        )

    @property
    def unique_id(self) -> str:
        """Set the unique id of the switch."""
        return f"{self._description.key}.switch"

    @property
    def is_on(self) -> bool:
        """Get the value of the switches underlying sensor."""
        # Use the sensor value to determine the state of the switch
        value = traverse_nested_dict(self.getCarByVin(self._vin), self._description.key)
        return value == self._description.enabled_value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        # Call the API to start charging
        if self._description.enabled_func is None:
            return
        await self._description.enabled_func(self._session, self._vin, self._apiKey)

        for vehicle in self.coordinator.data["results"]:
            if vehicle["vin"] == self._vin:
                set_nested_dict_value(
                    vehicle, self._description.key, self._description.enabled_value
                )
                break
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        # Call the API to stop charging
        if self._description.disabled_func is None:
            return
        await self._description.disabled_func(self._session, self._vin, self._apiKey)

        for vehicle in self.coordinator.data["results"]:
            if vehicle["vin"] == self._vin:
                set_nested_dict_value(
                    vehicle, self._description.key, self._description.disabled_value
                )
                break

        self.async_write_ha_state()


SENSOR_INFO_TYPES_TESLA: tuple[TessieSwitchEntityDescription, ...] = (
    TessieSwitchEntityDescription(
        translation_key="charging_state_switch",
        key="last_state.charge_state.charging_state",
        switchName="Tesla Charger",
        enabled_func=start_charging,
        enabled_value="Charging",
        disabled_func=stop_charging,
        disabled_value="Stopped",
    ),
)
