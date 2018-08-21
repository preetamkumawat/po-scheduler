from flask import Flask, render_template, request, Response
from scheduler import get_docks_from_db, get_inbounds_from_db, calculate_schedules, po_from_csv, docks_from_csv_to_db

app = Flask(__name__)


def stream_template(template_name, ** context):
    """Streaming content and sending on the fly instead of storing in memory"""
    app.update_template_context(context)
    t = app.jinja_env.get_template(template_name)
    rv = t.stream(context)
    rv.enable_buffering(5)
    return rv


@app.route("/", methods=["GET", "POST"])
def index():
    """PO upload front view"""
    results = []
    if request.method == "POST":
        request_file = request.files['file'].read()
        pos = po_from_csv(request_file)
        docks = get_docks_from_db()

        if len(list(set(['po_id', 'item_id', 'quantity']) & set(pos[0].keys()))) != 3:
            data = {"message": "Invalid File uploaded", "status": 400}
        elif not docks:
            data = {"message": "Docks missing", "status": 400}
        elif not pos:
            data = {"message": "No POs in file", "status": 400}
        else:
            results = calculate_schedules(pos, docks)
            if results:
                data = {"message": "Done", "status": 200}
            else:
                results = []
                data = {"message": "Couldn't calculate schedules!", "status": 201}

        return Response(stream_template('index.html', results=results, error=0, data=data))
    else:
        return render_template('index.html', results=results, error=0)


@app.route("/upload_docks", methods=["GET", "POST"])
def upload_docks():
    """
    Dock upload view
    :return:
    """
    if request.method == "POST":
        request_file = request.files['file'].read()
        docks = docks_from_csv_to_db(request_file)

        if not docks:
            data = {"message": "No Docks in file", "status": 400}
        else:
            data = {"message": "Done", "status": 200}

        return Response(stream_template('docks_upload.html', error=0, data=data))
    else:
        return render_template('docks_upload.html', error=0)


@app.route("/history", methods=["GET", "POST"])
def history():
    results = get_inbounds_from_db()
    dock_dates = list(set([i['slot_start_date'].date() for i in results]))
    dock_ids = list(set([i['dock_id'] for i in results]))
    selected_slot = None
    selected_dock = None

    if request.method == "POST":
        selected_slot = request.form.get('slot_date', None)
        selected_dock = request.form.get('dock_id', None)

        results = [result for result in results
                   if (not selected_dock or str(result['dock_id']) == selected_dock)
                        and (not selected_slot or (selected_slot == str(result['slot_start_date'].date())
                                           or selected_slot == str(result['slot_end_date'].date())))]

    return render_template(
        'history.html',
        results=results,
        dock_dates=dock_dates,
        dock_ids=dock_ids,
        selected_slot=selected_slot,
        selected_dock=selected_dock
    )


if __name__ == "__main__":
    app.run(threaded=True, host='0.0.0.0', port=8080, debug=True)
