#!/usr/bin/env python3
from __future__ import annotations

import asyncio

from fixtures import VirtualCarSpeed
from _scenario_common import import_mape, load_hierarchical_module


async def main():
    mape = import_mape()
    hierarchical = load_hierarchical_module()

    mape.init(debug=False)

    car = VirtualCarSpeed(
        "Panda",
        speed=80,
        max_power=70,
        max_break=70,
        position=0,
    )
    car_in_front = VirtualCarSpeed(
        "Countach",
        speed=90,
        max_power=200,
        max_break=180,
        position=300,
    )

    await hierarchical.create_cruise_control(car)
    await hierarchical.create_cruise_control(car_in_front)
    await hierarchical.create_hold_distance(car, car_in_front)

    car.position = 30
    car_in_front.position = 260
    await asyncio.sleep(0.30)

    car.position = 80
    car_in_front.position = 250
    await asyncio.sleep(0.30)

    car.position = 120
    car_in_front.position = 240
    await asyncio.sleep(0.30)


if __name__ == "__main__":
    asyncio.run(main())
