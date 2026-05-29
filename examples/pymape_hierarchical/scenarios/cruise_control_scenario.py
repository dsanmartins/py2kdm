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

    await hierarchical.create_cruise_control(car)

    car.speed = 70
    await asyncio.sleep(0.25)

    car.speed = 130
    await asyncio.sleep(0.25)

    car.speed = 95
    await asyncio.sleep(0.25)

    planner = mape.app["cruise_control_Panda.pid"]
    planner.cruise_control(90)

    car.speed = 100
    await asyncio.sleep(0.25)


if __name__ == "__main__":
    asyncio.run(main())
