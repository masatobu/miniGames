import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from pyxel_background_worker.logic import (  # pylint: disable=C0413
    GameLogic,
    Job,
    Resource,
    Building,
)


class TestGameLogic(unittest.TestCase):
    def test_add_worker(self):
        game_logic = GameLogic()
        self.assertEqual(game_logic.get_worker_num(), 0)
        worker_id = game_logic.add_worker()
        self.assertEqual(game_logic.get_worker_num(), 1)
        self.assertEqual(worker_id, 0)

    def test_set_worker_job(self):
        test_cases = [
            ("FARMER", 1, Job.FARMER, 1, {}, Building.FARM),
            ("BUILDER", 1, Job.BUILDER, 1, {}, Building.FARM),
            ("LOGGER", 1, Job.LOGGER, 1, {}, Building.WOODSHED),
            ("NO JOB", 1, None, 1, {}, None),
            ("over FARMER", 4, Job.FARMER, 5, {Building.HOUSE: 2}, Building.FARM),
            ("many BUILDER", 5, Job.BUILDER, 5, {Building.HOUSE: 2}, Building.FARM),
            ("over LOGGER", 4, Job.LOGGER, 5, {Building.HOUSE: 2}, Building.WOODSHED),
            (
                "5 FARMER",
                5,
                Job.FARMER,
                5,
                {Building.HOUSE: 2, Building.FARM: 2},
                Building.FARM,
            ),
            (
                "5 LOGGER",
                5,
                Job.LOGGER,
                5,
                {Building.HOUSE: 2, Building.WOODSHED: 2},
                Building.WOODSHED,
            ),
        ]
        for case_name, expected, job, num, building_map, place in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                job=job,
                num=num,
                building_map=building_map,
                place=place,
            ):
                game_logic = GameLogic()
                game_logic.building_num_map |= building_map
                for i in range(num):
                    worker_id = game_logic.add_worker()
                    game_logic.set_worker_job(worker_id, job, place)
                    self.assertEqual(
                        game_logic.get_worker_job(worker_id),
                        job if i < expected else None,
                    )
                    self.assertEqual(
                        game_logic.get_worker_place(worker_id),
                        place if i < expected else None,
                    )

    def test_turn(self):
        test_cases = [
            ("1 farmer 1 turn", {Resource.FOOD: 1}, {Job.FARMER: 1}, 1, 1),
            ("2 farmer 1 turn", {Resource.FOOD: 2}, {Job.FARMER: 2}, 1, 1),
            ("2 farmer 2 turn", {Resource.FOOD: 4}, {Job.FARMER: 2}, 2, 1),
            (
                "2 farmer 2 builder 2 turn",
                {Resource.FOOD: 0},
                {Job.FARMER: 2, Job.BUILDER: 2},
                2,
                1,
            ),
            (
                "2 logger 2 builder 2 turn",
                {Resource.WOOD: 4},
                {Job.LOGGER: 2, Job.BUILDER: 2},
                2,
                1,
            ),
            (
                "2 logger 2 farmer 2 turn",
                {Resource.WOOD: 8, Resource.FOOD: 0},
                {Job.LOGGER: 2, Job.FARMER: 2},
                2,
                1,
            ),
            (
                "5 farmer 0 house, and 1 got out",
                {Resource.FOOD: 4},
                {Job.FARMER: 5},
                1,
                1,
            ),
            (
                "9 farmer 1 house, and 1 got out",
                {Resource.FOOD: 8},
                {Job.FARMER: 9},
                1,
                2,
            ),
        ]
        for case_name, expected, worker_num_map, turn_num, house_num in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                worker_num_map=worker_num_map,
                turn_num=turn_num,
                house_num=house_num,
            ):
                game_logic = GameLogic()
                game_logic.building_num_map = {b: house_num for b in Building}
                for job, num in worker_num_map.items():
                    for _ in range(num):
                        worker_id = game_logic.add_worker()
                        if worker_id is not None:
                            game_logic.set_worker_job(
                                worker_id,
                                job,
                                game_logic.JOB_BUILDING_MAP.get(job, Building.FARM),
                            )
                expected_resources = {r: 0 for r in Resource}
                self.assertEqual(game_logic.resource_map, expected_resources)
                for _ in range(turn_num):
                    game_logic.turn()
                expected_resources |= expected
                self.assertEqual(game_logic.resource_map, expected_resources)

    def test_turn_consume(self):
        test_cases = [
            ("1 no farmer", 0, {Job.LOGGER: 1}),
            ("1 farmer", 1, {Job.FARMER: 1}),
        ]
        for case_name, expected, worker_job_map in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                worker_job_map=worker_job_map,
            ):
                game_logic = GameLogic()
                population = 0
                for job, num in worker_job_map.items():
                    population += num
                    for _ in range(num):
                        worker_id = game_logic.add_worker()
                        game_logic.set_worker_job(
                            worker_id, job, game_logic.JOB_BUILDING_MAP[job]
                        )
                self.assertEqual(game_logic.get_worker_num(), population)
                game_logic.turn()
                self.assertEqual(game_logic.get_worker_num(), expected)

    def test_turn_building(self):
        def _check_building_state(
            game_logic,
            expected_num,
            expected_progress,
            expected_time_cost,
            expected_resource,
            building,
        ):
            self.assertEqual(game_logic.get_building_num(building), expected_num)
            self.assertEqual(game_logic.get_build_progress(building), expected_progress)
            self.assertEqual(game_logic.get_time_cost(building), expected_time_cost)
            self.assertEqual(game_logic.resource_map[Resource.WOOD], expected_resource)

        test_cases = [
            ("1 HOUSE by 1", 3, 3, Building.HOUSE, 1, 1),
            ("1 FARM by 1", 3, 3, Building.FARM, 1, 1),
            ("1 HOUSE by 2", 2, 3, Building.HOUSE, 2, 1),
            ("2 HOUSE by 1", 6, 6, Building.HOUSE, 1, 2),
        ]
        for (
            case_name,
            expected_build_turn,
            expected_time_cost,
            building,
            worker_num,
            building_num,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_build_turn=expected_build_turn,
                expected_time_cost=expected_time_cost,
                building=building,
                worker_num=worker_num,
                building_num=building_num,
            ):
                game_logic = GameLogic()
                resource_count = 5 * 2 ** (building_num - 1)
                game_logic.resource_map |= {
                    Resource.WOOD: resource_count,
                    Resource.FOOD: 10000000,
                }
                game_logic.building_num_map[building] = building_num
                for _ in range(worker_num):
                    worker_id = game_logic.add_worker()
                    game_logic.set_worker_job(worker_id, Job.BUILDER, building)
                check_param = [
                    game_logic,
                    building_num,
                    0,
                    expected_time_cost,
                    resource_count,
                    building,
                ]
                _check_building_state(*check_param)
                game_logic.turn()
                check_param[2:5] = [worker_num, expected_time_cost, 0]
                _check_building_state(*check_param)
                for _ in range(expected_build_turn - 1):
                    game_logic.turn()
                check_param[1:4] = [building_num + 1, 0, expected_time_cost * 2]
                _check_building_state(*check_param)
                game_logic.turn()
                _check_building_state(*check_param)

    def test_pay_building_cost(self):
        test_cases = [
            ("HOUSE", True, Building.HOUSE, 1, {Resource.WOOD: 5}),
            ("No Resource", False, Building.HOUSE, 1, {Resource.WOOD: 0}),
            ("2 HOUSE", True, Building.HOUSE, 2, {Resource.WOOD: 10}),
            ("3 HOUSE", True, Building.HOUSE, 3, {Resource.WOOD: 20}),
            ("FARM", True, Building.FARM, 1, {Resource.WOOD: 5}),
            ("WOODSHED", True, Building.WOODSHED, 1, {Resource.WOOD: 5}),
        ]
        for case_name, expected, building, build_num, resource in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                building=building,
                build_num=build_num,
                resource=resource,
            ):
                game_logic = GameLogic()
                game_logic.resource_map |= resource
                game_logic.building_num_map[building] = build_num
                ret = game_logic._pay_builing_cost(building)  # pylint: disable=W0212
                self.assertEqual(ret, expected)
                self.assertEqual(
                    all(game_logic.resource_map[r] == 0 for r in Resource), True
                )

    def test_get_resource_change(self):
        test_cases = [
            ("no worker", {Resource.FOOD: 0}, 0, (None, None), 0),
            ("1 worker", {Resource.FOOD: -1}, 1, (None, None), 0),
            ("2 worker", {Resource.FOOD: -2}, 2, (None, None), 0),
            ("1 farmer", {Resource.FOOD: 2}, 1, (Job.FARMER, Building.FARM), 1),
            ("2 farmer", {Resource.FOOD: 4}, 2, (Job.FARMER, Building.FARM), 2),
            ("1 logger", {Resource.WOOD: 2}, 1, (Job.LOGGER, Building.WOODSHED), 1),
            ("2 logger", {Resource.WOOD: 4}, 2, (Job.LOGGER, Building.WOODSHED), 2),
            ("1 farm builder", {Resource.WOOD: -5}, 1, (Job.BUILDER, Building.FARM), 1),
            (
                "2 farm builder",
                {Resource.WOOD: -10},
                1,
                (Job.BUILDER, Building.FARM),
                2,
            ),
            (
                "3 farm builder",
                {Resource.WOOD: -20},
                1,
                (Job.BUILDER, Building.FARM),
                3,
            ),
            (
                "1 woodshed builder",
                {Resource.WOOD: -5},
                1,
                (Job.BUILDER, Building.WOODSHED),
                1,
            ),
            (
                "2 woodshed builder",
                {Resource.WOOD: -10},
                1,
                (Job.BUILDER, Building.WOODSHED),
                2,
            ),
            (
                "3 woodshed builder",
                {Resource.WOOD: -20},
                1,
                (Job.BUILDER, Building.WOODSHED),
                3,
            ),
            (
                "1 house builder",
                {Resource.WOOD: -5},
                1,
                (Job.BUILDER, Building.HOUSE),
                1,
            ),
            (
                "2 house builder",
                {Resource.WOOD: -10},
                1,
                (Job.BUILDER, Building.HOUSE),
                2,
            ),
            (
                "3 house builder",
                {Resource.WOOD: -20},
                1,
                (Job.BUILDER, Building.HOUSE),
                3,
            ),
        ]
        for case_name, expected, worker_num, job_place, target_num in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                worker_num=worker_num,
                job_place=job_place,
                target_num=target_num,
            ):
                game_logic = GameLogic()
                for _ in range(worker_num):
                    game_logic.add_worker()
                if job_place[0] is Job.BUILDER:
                    game_logic.building_num_map[job_place[1]] = target_num
                else:
                    for i in range(target_num):
                        game_logic.set_worker_job(i, *job_place)
                self.assertEqual(game_logic.get_resource_change(*job_place), expected)

    def test_to_from_dict(self):
        test_cases = [
            ("data with 1 worker", 1),
            ("data with 2 worker", 2),
            ("No data", None),
        ]
        for case_name, worker in test_cases:
            with self.subTest(case_name=case_name, worker=worker):
                dump = None
                if worker is not None:
                    game_logic = GameLogic()
                    for _ in range(worker):
                        game_logic.add_worker()
                    dump = game_logic.to_dict()
                game_logic = GameLogic.from_dict(dump)
                self.assertEqual(
                    game_logic.get_worker_num(), worker if worker is not None else 0
                )
                self.assertEqual(game_logic.get_building_num(Building.HOUSE), 1)

    def test_get_message(self):
        game_logic = GameLogic()
        self.assertEqual(game_logic.get_message(), "test")


if __name__ == "__main__":
    unittest.main()
