"""Sensor for retrieving data for SEMS portal."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, TessieDataUpdateCoordinator
from .entity import BaseTessieSensor


def traverse_nested_dict(data_dict, key_path):
    """Get a value by a dot notation."""

    keys = key_path.split(".")
    value = data_dict
    for key in keys:
        value = value.get(key)
        if value is None:
            return None
    return value


class TessieCarSensor(BaseTessieSensor):
    """Used to represent a SemsInformationSensor."""

    def getCarByVin(self, coordinator: TessieDataUpdateCoordinator, vin: str) -> Any:
        """Retrieve the inverter by name."""

        for car in coordinator.data["results"]:
            if car["vin"] == vin:
                return car
        return None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return traverse_nested_dict(
            self.getCarByVin(self.coordinator, self.vin), self.entity_description.key
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Get the setup sensor."""

    coordinator: TessieDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    cars = coordinator.data["results"]

    teslaCarInfoEntities = [
        TessieCarSensor(
            car["last_state"]["display_name"],
            car["last_state"]["vehicle_config"]["car_type"],
            car["vin"],
            config_entry,
            description,
            coordinator,
        )
        for description in SENSOR_INFO_TYPES_TESLA
        for car in cars
    ]

    async_add_entities(teslaCarInfoEntities)


SENSOR_INFO_TYPES_TESLA: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        translation_key="display_name",
        key="last_state.display_name",
        native_unit_of_measurement=None,
        device_class=None,
    ),
)
