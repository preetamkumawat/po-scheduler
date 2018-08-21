import io
from collections import defaultdict
from operator import itemgetter
import csv
from utils import get_results_as_dict, write_to_db
from models import Dock, PurchaseOrder, ItemInbound


def parse_file(file=None):
    """
    Takes file's path or filestorage obj if its an upload and returns its content in list
    :param file: str or bytes
    :return: list | file content
    """

    try:
        if type(file) == bytes:
            decoded_file = file.decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            return list(reader)
        else:
            with open(file, newline='') as csv_file:
                reader = csv.DictReader(csv_file)
                return list(reader)
    except FileNotFoundError:
        return []
    except OSError:
        return []


def po_from_csv(file, save_to_db=False):
    """
    Takes a CSV file as input and return its content as list. Saves them in db is save_to_db is true
    :param file: str po file
    :param save_to_db: boolean
    :return: list | po data
    """
    po_data = parse_file(file)

    if not save_to_db:
        return po_data

    query = "INSERT INTO po_scheduler.po_items (item_id, po_id, quantity) VALUES {values}"
    values = []

    if len(list(set(['po_id', 'item_id', 'quantity']) & set(po_data[0].keys()))) != 3:
        return []

    for data in po_data:
        values.append("({}, {}, {})".format(data['item_id'], data['po_id'], data['quantity']))

    if not values:
        return []

    write_to_db(query.format(values=", ".join(values)))
    return po_data


def docks_from_csv_to_db(file):
    """
    Takes a CSV file path or FileStorage obj and returns list of all docks. Saves the docks in db.
    :param file: str or FileStorage
    :return: list of all docks
    """

    dock_data = parse_file(file)
    query = "INSERT INTO po_scheduler.dock_slots (dock_id, slot_start_date, slot_end_date, capacity) VALUES {values};"
    values = []

    if len(list(set(['dock_id', 'slot_start_dt', 'slot_end_dt', 'capacity']) & set(dock_data[0].keys()))) != 4:
        return []

    for data in dock_data:
        values.append("({}, '{}', '{}', {})".format(
            data['dock_id'],
            data['slot_start_dt'].replace("T", " "),
            data['slot_end_dt'].replace("T", " "),
            data['capacity'])
        )

    if not values:
        return []

    write_to_db(query.format(values=", ".join(values)))
    return dock_data


def get_docks_from_db():
    """
    Returns dock slots saved in db
    :return: list
    """
    query = "SELECT * FROM po_scheduler.dock_slots;"

    return get_results_as_dict(query)


def get_inbounds_from_db():
    """
    Returns history of inbound records created with previous PO uploads
    :return: list
    """
    query = "SELECT * FROM po_scheduler.item_inbound;"

    return get_results_as_dict(query)


def save_inbound_to_db(inbounds):
    """
    Saves our scheduled POs to DB
    :param inbounds: list of inbound schedules
    :return: None
    """
    query = """INSERT INTO po_scheduler.item_inbound (
    dock_id, 
    item_id, 
    po_id, 
    quantity, 
    slot_start_date, 
    slot_end_date) VALUES {values} ON DUPLICATE KEY UPDATE quantity=quantity;"""

    values = []

    for inbound in inbounds:
        values.append("({}, {}, {}, {}, '{}', '{}')".format(
            inbound['dock_id'],
            inbound['item_id'],
            inbound['po_id'],
            inbound['quantity'],
            inbound['slot_start_date'],
            inbound['slot_end_date'])
        )

        if not values:
            return []

    write_to_db(query.format(values=", ".join(values)))


def arrange_pos(pos):
    """
    Takes pos as list, Instantiates PurchaseOrder modules object and returns a dict will all PO objects
    :param pos: list | of all POs (directly taken from file)
    :return: dict | PO objects arranged by po_ids
    """
    arranged_pos = defaultdict(list)
    po_objects = []

    for po in pos:
        # First we combine all items belonging to different POs
        # So it'll look like {'1': [{item1}, {item2}, {item3}], '2': [{item4}]}
        arranged_pos[po['po_id']].append({
            "item_id": po['item_id'],
            "quantity": int(po['quantity'])
        })

    for po in arranged_pos.items():
        # Now we instantiate PurchaseOrder object. tupple po has ID on 0th Index and items on 1st index
        po_obj = PurchaseOrder(po[0])

        # Add Items to it
        po_obj.insert_multiple_items(po[1])

        # Finally Add our newly created PurchaseOrder to out Po list
        po_objects.append(po_obj)

    return po_objects


def arrange_slots(slots):
    """
    Arranging all docks according to different slots. We are not instantiating Dock objects yet.
    Reason for that is to reuse same Dock objects across different slots.
    :param slots: list of all slots
    :return: sorted list of all Slots with docks in them
    """
    arranged_slots = defaultdict(list)

    # We need the maximum capacity of all docks across all the slots.
    dock_max_capacities = {}

    # Why 2 loops? Well we need the max capacity prior to organizing the docks in slots
    for slot in slots:
        slot['capacity'] = int(slot['capacity'])
        if dock_max_capacities.get(slot['dock_id'], 0) < slot['capacity']:
            dock_max_capacities[slot['dock_id']] = slot['capacity']

    for slot in slots:
        arranged_slots["{}:{}".format(
            slot['slot_start_date'],
            slot['slot_end_date']
        )].append({
            **slot,
            'max_capacity': dock_max_capacities.get(slot['dock_id'])
        })

    # It'll look like as below:
    # [
    #   ('2018-08-01T00:00:00:2018-08-01T01:00:00',
    #       [{
    #           'dock_id': '1',
    #           'slot_start_date': '2018-08-01T00:00:00',
    #           'slot_end_date': '2018-08-01T01:00:00',
    #           'capacity': 183,
    #           'max_capacity': 236
    #       }]
    #   )
    # ]
    return sorted(arranged_slots.items())


def get_dock_for_po(items, docks):
    """
    This takes in items of a PO and checks with Knapsack algorithm to figure out
    which Dock has the best capacity available to organize item with least unused space for a given slot.
    :param items: list of items in a PO
    :param docks: dict | all the docks in current slot
    :return: Dock obj or None, list of best combination to fill the dock
    """
    possible_docks = {}
    possible_dock_objects = {}
    items_in_dock = {}

    for id, dock in docks.items():
        possible_dock_objects[dock.dock_id] = dock

        if dock.po_id is None and dock.capacity > 0:
            # We're looking for best Item combination here. This will determine which dock to select
            # and which items to unload
            dock_items = fill_items_in_dock(items, dock.capacity)

            # We're checking how much unused space is left in a dock after items have been filled.
            possible_docks[dock.dock_id] = dock.capacity - sum([item['quantity'] for item in dock_items])
            items_in_dock[dock.dock_id] = dock_items

            # # If Knapsack seems too much then we can use my older but less accurate version to select a dock.
            # for item in items:
            #     if item['quantity'] <= min(dock.capacity, possible_docks[dock.dock_id]):
            #         possible_docks[dock.dock_id] -= item['quantity']

    # We're taking the dock with least unused space and the items to fill in it.
    for dock_id, val in sorted(possible_docks.items(), key=itemgetter(1)):
        return possible_dock_objects[dock_id], items_in_dock[dock_id]

    return None, []


def remove_invalid_items(pos, docks):
    """
    This is a helper function to remove all items from POs which cannot be unloaded at any dock in any slot.
    :param pos: list | of all POs
    :param docks: Docks objects.
    :return: None
    """
    if not docks:
        return

    docks_max_capacities = sorted([int(dock['max_capacity']) for dock in docks[1]])

    for po in pos:
        po.items = [item for item in po.items if 0 < item['quantity'] <= docks_max_capacities[-1]]


def fill_items_in_dock(items, capacity):
    """
    Implementation of Knapsack algorithm. Three consecutive loops to check the best possible combination
    of items to fill in a dock.
    A better way would have been to keep the function recursive and then check the combinations.
    :param items: list of items
    :param capacity: Integer capacity of the given dock.
    :return: list of items to be filled in the dock
    """

    # This holds all combinations that can be filled in the dock.
    possible_combinations = {}

    iteration = 0

    for i in range(len(items)):
        if items[i]['quantity'] == capacity:
            # We've found the one item which will take in all the capacity of the dock
            possible_combinations[iteration] = [items[i]]
            break
        elif items[i]['quantity'] > capacity:
            # This item is too large to fill in this dock in current slot
            continue

        for j in range(i+1, len(items)):
            possible_combinations[iteration] = [items[i]]
            current_total = items[i]['quantity'] + items[j]['quantity']

            if current_total == capacity:
                possible_combinations[iteration].append(items[j])
                break
            elif current_total > capacity:
                continue

            possible_combinations[iteration].append(items[j])

            for n in range(j+1, len(items)):
                if items[n]['quantity'] + current_total == capacity:
                    current_total += items[n]['quantity']
                    possible_combinations[iteration].append(items[n])
                    break
                elif items[n]['quantity'] + current_total < capacity:
                    current_total += items[n]['quantity']
                    possible_combinations[iteration].append(items[n])
                else:
                    continue

            iteration += 1
        else:
            possible_combinations[iteration] = [items[i]]

        iteration += 1

    result = []
    # This is to check which item has the least unused space.
    difference = capacity

    for items in possible_combinations.values():
        items_sum = sum([i['quantity'] for i in items])
        # if items sum and capacity different is less then the currently held item then we've got a new winner.
        if capacity - items_sum < difference:
            difference = capacity - items_sum
            result = items

    return result


def check_performance(docks):
    """
    This function checks the performance of a Slot once we've filled in all the POs in it.
    :param docks: all docks available in the slot
    :return: float number with performance index
    """
    capacity_ratio_sum = 0

    for dock in docks.values():
        capacity_ratio_sum += dock.capacity/dock.slot_capacity

    return capacity_ratio_sum/len(docks)


def calculate_schedules(po_list, slot_list):
    """
    Star function. Takes POs and Docks as input. Docks will be arranged slot wise. Calculates schedules per slot
    and docks performances. Saves inbound data and performances in CSV files.
    :param po_list: list of all pos to inbound
    :param slot_list: list of all docks available sorted in slots. Slots are sorted in ascending order
    :return: inbound results
    """

    # Arrange our items according to their POs
    pos = arrange_pos(po_list)

    # Arrange our docks according to their slots
    slots = arrange_slots(slot_list)

    docks = {}
    outputs = []
    performances = []

    if not slots:
        return []

    # remove all items which can never be inbounded
    remove_invalid_items(pos, slots[0])

    # Loop through slots
    for slot, docks_dict in slots:

        # Instantiate all Docks and append them in separate dic
        for dock in docks_dict:
            if docks.get(dock['dock_id'], None):
                docks[dock['dock_id']].set_slot_values(dock['capacity'], dock['slot_start_date'], dock['slot_end_date'])
            else:
                docks[dock['dock_id']] = Dock(
                    dock['dock_id'],
                    dock['slot_start_date'],
                    dock['slot_end_date'],
                    dock['capacity'],
                    dock['max_capacity']
                )

        # Loop through all pos and inbound them to docks
        for po in pos:
            if not po.items:
                continue

            # If a po already belongs to a Dock, which can happen if Po has items bigger then docks slot capacity,
            # then this property of po will be set already
            if po.dock_id:
                current_dock = docks.get(po.dock_id)
                items_to_fill = fill_items_in_dock(po.items, current_dock.capacity)
            else:
                # So our PO is a new one and doesn't belong to any Dock. Lets find a dock for it. And a list of items
                # in best possible way to inbound for this slot capacity.
                current_dock, items_to_fill = get_dock_for_po(po.items, docks)

            if not current_dock:
                # So we couldn't find any dock for our poor po. Don't worry there's always another time to inbound.
                continue

            # found a dock, good, let's set the properties accordingly
            current_dock.occupy_dock(po.po_id)

            # PO should know which dock it belongs to
            po.set_dock(current_dock.dock_id)

            # Now lets inbound items.
            for item in items_to_fill:
                # Unloading items...
                check, message = current_dock.inbound_item_to_dock(item['quantity'])

                if not check:
                    # This is rather shameful with all the checks we have done previously. Lets hope we never come here.
                    if message == "capacity_full":
                        break
                    elif message == "capacity_exceeded":
                        pass
                    else:
                        continue
                else:
                    # Alrighty, good part is done. Now lets save our results
                    outputs.append({
                        "slot_start_date": current_dock.slot_start_date,
                        "slot_end_date": current_dock.slot_end_date,
                        "dock_id": current_dock.dock_id,
                        "po_id": current_dock.po_id,
                        "item_id": item["item_id"],
                        "quantity": item["quantity"],
                        "dock_current_capacity": current_dock.capacity
                    })

                    # This is for future development. No need for now.
                    ItemInbound(
                        current_dock.slot_start_date,
                        current_dock.slot_end_date,
                        current_dock.dock_id,
                        current_dock.po_id,
                        item["item_id"],
                        item['quantity']
                    )

                # So our item was inbounded. Lets remove it from PO
                item['remove'] = True

            # PO should only contain items which aren't yet inbounded
            po.items = [item for item in po.items if not item.get('remove', False)]

            # If all items from PO are in dock, then lets release the dock to be used further
            if not po.items:
                current_dock.release_dock()
                po.release_dock()

        # Calculate performances.
        performances.append({
            "slot_start_date": docks_dict[0]['slot_end_date'],
            "slot_end_date": docks_dict[0]['slot_start_date'],
            "performance": check_performance(docks)
        })

    # Save our finding to files. Can be dynamic file names for daily record.
    output_to_csv(outputs, "po_schedular_output.csv")
    output_to_csv(performances, "slot_performances.csv")

    # Now lets save our inbound results to db
    save_inbound_to_db(outputs)
    return outputs


def output_to_csv(outputs, file):
    """
    Writes the output to a file
    :param outputs:
    :return:
    """
    if not outputs:
        return

    with open(file, 'w+') as f:
        w = csv.DictWriter(f, outputs[0].keys())
        w.writeheader()

        for output in outputs:
            w.writerow(output)
