from node import NodeManager
from edge import EdgeDirect, EdgeManager


class MaterialFlow:
    def process(self, node_manager: NodeManager, edge_manager: EdgeManager):
        self._produce_pure(node_manager)
        self._transfer(node_manager, edge_manager)
        self._produce_conditional(node_manager)
        self._level_up_nodes(node_manager)
        self._decay_maintenance_nodes(node_manager)

    def _produce_pure(self, node_manager: NodeManager):
        for col, row in node_manager.positions():
            node = node_manager.get_node(col, row)
            if (
                node.params.consumption_stock_cols
                or not node.params.production_stock_cols
            ):
                continue
            for material, rate in node.params.production_rates.items():
                node.add_production_stock(material, rate)

    def _transfer(self, node_manager: NodeManager, edge_manager: EdgeManager):
        edge_manager.reset_directs()
        transfer_plan = {}  # {(src_pos, material): [dest_node, ...]}
        for start, end in edge_manager.endpoint_pairs():
            n1 = node_manager.get_node(*start)
            n2 = node_manager.get_node(*end)
            for material in n1.params.production_stock_cols:
                if self._can_receive(n2, material):
                    transfer_plan.setdefault((start, material), []).append(n2)
            for material in n2.params.production_stock_cols:
                if self._can_receive(n1, material):
                    transfer_plan.setdefault((end, material), []).append(n1)
        for (src_pos, material), dests in transfer_plan.items():
            source = node_manager.get_node(*src_pos)
            if not self._can_send(source, material):
                continue
            self._transfer_material(source, dests, material)
            for dest in dests:
                edge = edge_manager.get_edge(src_pos, (dest.col, dest.row))
                direct = (
                    EdgeDirect.FORWARD if src_pos == edge.start else EdgeDirect.BACKWARD
                )
                edge.set_direct(direct)

    def _can_send(self, node, material) -> bool:
        return node.get_production_stock(material) > 0

    def _can_receive(self, node, material) -> bool:
        if material in node.params.consumption_rates:
            return (
                node.get_consumption_stock(material)
                < node.params.consumption_rates[material]
            )
        if material in node.params.growth_limits:
            return node.get_growth_stock(material) < node.params.growth_limits[material]
        return False

    def _need(self, node, material) -> int:
        if material in node.params.consumption_rates:
            return node.params.consumption_rates[material] - node.get_consumption_stock(
                material
            )
        return node.params.growth_limits[material] - node.get_growth_stock(material)

    def _add_dest_stock(self, node, material, num):
        if material in node.params.consumption_rates:
            node.add_consumption_stock(material, num)
        else:
            node.add_growth_stock(material, num)

    def _produce_conditional(self, node_manager: NodeManager):
        for col, row in node_manager.positions():
            node = node_manager.get_node(col, row)
            if (
                not node.params.consumption_stock_cols
                or not node.params.production_stock_cols
            ):
                continue
            for material, rate in node.params.consumption_rates.items():
                if node.get_consumption_stock(material) < rate:
                    continue
                node.subtract_consumption_stock(material, rate)
                for prod_material, prod_rate in node.params.production_rates.items():
                    node.add_production_stock(prod_material, prod_rate)

    def _level_up_nodes(self, node_manager: NodeManager):
        for col, row in node_manager.positions():
            node = node_manager.get_node(col, row)
            if node.is_maintenance_mode:
                continue
            if node.is_growth_complete():
                node.level_up()

    def _decay_maintenance_nodes(self, node_manager: NodeManager):
        for col, row in node_manager.positions():
            node = node_manager.get_node(col, row)
            if not node.is_maintenance_mode:
                continue
            for material, decay_rate in node.params.consumption_rates.items():
                buffered = node.get_consumption_stock(material)
                net_delta = buffered - decay_rate
                node.subtract_consumption_stock(material, buffered)
                if net_delta >= 0:
                    node.add_growth_stock(material, net_delta)
                else:
                    node.subtract_growth_stock(material, -net_delta)
                if node.get_growth_stock(material) <= 0:
                    node.level_down()
                    break

    def _transfer_material(self, source, destinations, material):
        stock = source.get_production_stock(material)
        needs = [self._need(d, material) for d in destinations]
        total_need = sum(needs)
        if total_need <= stock:
            for d, need in zip(destinations, needs):
                self._add_dest_stock(d, material, need)
            source.subtract_production_stock(material, total_need)
        else:
            share = stock // len(destinations)
            for d in destinations:
                self._add_dest_stock(d, material, share)
            source.subtract_production_stock(material, stock)
