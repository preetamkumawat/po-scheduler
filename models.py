class Dock:
    def __init__(self, dock_id, start, end, capacity, max_capacity=None):
        self.po_id = None
        self.dock_id = dock_id
        self.slot_start_date = start
        self.slot_end_date = end
        self.capacity = capacity
        self.slot_capacity = capacity
        self.max_capacity = max_capacity

    def set_max_capacity(self, capacity):
        self.max_capacity = capacity

    def set_slot_values(self, capacity, start, end):
        self.capacity = capacity
        self.slot_capacity = capacity
        self.slot_start_date = start
        self.slot_end_date = end

    def occupy_dock(self, po_id):
        if self.capacity > 0:
            self.po_id = po_id
            return True, "dock_occupied"
        else:
            return False, "no_capacity"

    def release_dock(self):
        self.po_id = None

    def inbound_item_to_dock(self, quantity):
        if self.capacity == 0:
            return False, "capacity_full"
        elif quantity > self.max_capacity:
            return False, "capacity_exceeded"
        elif quantity > self.capacity:
            return False, "inbounded_failed_quantity"

        self.capacity -= int(quantity)
        return True, ""


class Item:
    def __init__(self, item_id, quantity):
        self.item_id = item_id
        self.quantity = quantity


class PurchaseOrder:
    def __init__(self, po_id):
        self.po_id = po_id
        self.items = []
        self.dock_id = None

    def set_dock(self, dock_id):
        self.dock_id = dock_id

    def release_dock(self):
        self.dock_id = None

    def insert_item(self, item):
        self.items.append(item)

    def insert_multiple_items(self, items):
        self.items += items

    def get_items(self):
        return self.items


class ItemInbound:
    def __init__(self, start, end, dock_id, po_id, item_id, quantity):
        self.slot_start_date = start
        self.slot_end_date = end
        self.dock_id = dock_id
        self.po_id = po_id
        self.item_id = item_id
        self.quantity = quantity
