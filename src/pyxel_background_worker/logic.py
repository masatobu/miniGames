from enum import Enum


class Job(Enum):
    FARMER = 0
    BUILDER = 1
    LOGGER = 2


class Resource(Enum):
    FOOD = 0
    WOOD = 1


class Building(Enum):
    HOUSE = 0
    FARM = 1
    WOODSHED = 2


class Worker:
    def __init__(self):
        self.job = None
        self.place = None

    def set_job(self, job, place):
        self.job = job
        self.place = place

    def get_job(self):
        return self.job

    def get_place(self):
        return self.place

    def to_dict(self):
        return {
            "job": getattr(self.job, "name", None),
            "place": getattr(self.place, "name", None),
        }

    @staticmethod
    def _get_data_property(data, cls):
        return cls[data] if data is not None else None

    @classmethod
    def from_dict(cls, data):
        worker = cls()
        job = cls._get_data_property(data["job"], Job)
        place = cls._get_data_property(data["place"], Building)
        worker.set_job(job, place)
        return worker


class GameLogic:
    JOB_RESOURCE_MAP = {
        Job.FARMER: Resource.FOOD,
        Job.LOGGER: Resource.WOOD,
    }
    JOB_BUILDING_MAP = {Job.FARMER: Building.FARM, Job.LOGGER: Building.WOODSHED}
    BUILDING_COST_MAP = {
        Building.HOUSE: {Resource.WOOD: 5},
        Building.FARM: {Resource.WOOD: 5},
        Building.WOODSHED: {Resource.WOOD: 5},
    }
    COLLECT_RATE = 2
    BUILDING_CAPACITY = 4
    BUILDING_BASE_WORKLOAD = 3

    def __init__(self):
        self.message = "test"
        self.workers = []
        self.resource_map = {r: 0 for r in Resource}
        self.building_num_map = {b: 1 for b in Building}
        self.build_workload_map = {b: 0 for b in Building}

    def add_worker(self) -> int | None:
        if self.BUILDING_CAPACITY * self.get_building_num(Building.HOUSE) <= len(
            self.workers
        ):
            return None
        self.workers.append(Worker())
        return len(self.workers) - 1

    def get_worker_num(self, job=None, place=None):
        return len(
            [
                worker
                for worker in self.workers
                if (job is None or worker.get_job() == job)
                and (place is None or worker.get_place() == place)
            ]
        )

    def get_building_num(self, building):
        return self.building_num_map[building]

    def _worker_id_check(self, worker_index):
        return worker_index is not None and 0 <= worker_index < len(self.workers)

    def set_worker_job(self, worker_index, job, place):
        if self._worker_id_check(worker_index):
            if job in [Job.BUILDER, None] or self.building_num_map[
                self.JOB_BUILDING_MAP[job]
            ] * self.BUILDING_CAPACITY > self.get_worker_num(job):
                self.workers[worker_index].set_job(job, place)

    def get_worker_job(self, worker_index):
        if self._worker_id_check(worker_index):
            return self.workers[worker_index].get_job()
        return None

    def get_worker_place(self, worker_index):
        if self._worker_id_check(worker_index):
            return self.workers[worker_index].get_place()
        return None

    def get_build_progress(self, building):
        return self.build_workload_map[building]

    def get_time_cost(self, building):
        return self.BUILDING_BASE_WORKLOAD * 2 ** (self.building_num_map[building] - 1)

    def get_resoruce(self, resource):
        return self.resource_map[resource]

    def get_resource_change(self, job, place) -> dict[Resource, int]:
        if job is None:
            return {Resource.FOOD: -1 * self.get_worker_num()}
        if job in [Job.FARMER, Job.LOGGER]:
            return {
                self.JOB_RESOURCE_MAP[job]: self.get_worker_num(job) * self.COLLECT_RATE
            }
        if job == Job.BUILDER:
            return {
                resource: base_cost * 2 ** (self.building_num_map[place] - 1) * -1
                for resource, base_cost in self.BUILDING_COST_MAP[place].items()
            }
        return {}

    def turn(self):
        self._turn_harvest()
        self._turn_build()
        self._turn_consume()

    def _turn_harvest(self):
        for job in self.JOB_RESOURCE_MAP:
            for resource, num in self.get_resource_change(job, None).items():
                self.resource_map[resource] += num

    def _turn_consume(self):
        degreese_list = []
        for resource, num in self.get_resource_change(None, None).items():
            self.resource_map[resource] += num
            result = self.resource_map[resource]
            if result < 0:
                degreese_list.append(result)
                self.resource_map[resource] = 0
        if len(degreese_list) > 0:
            self.workers = self.workers[: min(degreese_list)]

    def _pay_builing_cost(self, building) -> bool:
        new_resoruce_map = self.resource_map.copy()
        for resource, cost in self.get_resource_change(Job.BUILDER, building).items():
            if self.resource_map[resource] < cost * -1:
                return False
            new_resoruce_map[resource] += cost
        self.resource_map = new_resoruce_map
        return True

    def _turn_build(self):
        for building in Building:
            worker_num = self.get_worker_num(Job.BUILDER, building)
            if worker_num > 0:
                if self.get_build_progress(building) == 0:
                    if self._pay_builing_cost(building):
                        self.build_workload_map[building] = worker_num
                else:
                    self.build_workload_map[building] += worker_num
                    if self.get_build_progress(building) >= self.get_time_cost(
                        building
                    ):
                        self.build_workload_map[building] = 0
                        self.building_num_map[building] += 1

    def to_dict(self):
        return {
            "workers": [w.to_dict() for w in self.workers],
            "resource_map": {r.name: v for r, v in self.resource_map.items()},
            "building_num_map": {b.name: v for b, v in self.building_num_map.items()},
            "build_workload_map": {
                b.name: v for b, v in self.build_workload_map.items()
            },
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls()
        if data is not None:
            obj.workers = [Worker.from_dict(w) for w in data["workers"]]
            obj.resource_map = {Resource[r]: v for r, v in data["resource_map"].items()}
            obj.building_num_map = {
                Building[b]: v for b, v in data["building_num_map"].items()
            }
            obj.build_workload_map = {
                Building[b]: v for b, v in data["build_workload_map"].items()
            }
        return obj

    def get_message(self):
        return self.message
