import asyncio
import json
import logging
import os

import boto3
from chalice import Chalice, NotFoundError
from chalice.app import Rate

from chalicelib import helpers

app = Chalice(app_name="updatecheckerv2")

if 'AWS_CHALICE_CLI_MODE' not in os.environ:
    dynamodb = boto3.resource("dynamodb")
    sns = boto3.resource("sns")
    dynamodb_table = dynamodb.Table(os.environ.get("APP_TABLE_NAME", ""))
    notify_topic = sns.Topic(os.environ.get("NOTIFY_TOPIC", ""))

dynamodb_stream = os.environ.get("APP_TABLE_STREAM", "")
app.log.setLevel(logging.DEBUG)


@app.route("/software")
def list_software():
    """
    Provides a list of all supported software IDs.

    This returns only the identifiers of the software, to be used in later
    API calls for version information.
    """
    full_data = dynamodb_table.scan()["Items"]
    software_list = list(set([item["id"] for item in full_data]))
    return {"software": software_list}


@app.route("/software/{name}")
def get_latest_software(name):
    """
    Provides the information on all versions of the given sofware.
    """
    versions = helpers.get_all_versions(dynamodb_table, name)
    if not versions:
        raise NotFoundError(f"Cannot find {name}")
    return {name: versions}


@app.route("/software/{name}/{version}")
def get_software_version(name, version):
    """
    Provides information on a specific version of the given software.
    """
    item = helpers.get_software_version(dynamodb_table, name, version)
    if not item:
        raise NotFoundError(f"Cannot find {name} {version}")
    return item


@app.route('/refresh', methods=["POST"], api_key_required=True)
def refresh():
    asyncio.run(helpers.refresh_data(dynamodb_table, notify_topic, app.log))


@app.schedule(Rate(1, Rate.HOURS))
def update_data(event):
    """
    Update the cached data about software version.
    """
    asyncio.run(helpers.refresh_data(dynamodb_table, notify_topic, app.log))


@app.on_dynamodb_record(dynamodb_stream)
def send_update_notification(event):
    """
    Send an update to SNS when the table is updated.
    """
    updates = []
    for record in event:
        # Skip delete events and events for the non-latest
        if record.event_name == "DELETE":
            app.log.info("Skipping delete event")
            continue
        if not record.keys["SK"]["S"].endswith("latest"):
            continue
        if not record.new_image:
            app.log.warn("Got a MODIFY/INSERT without new_image: %s", record.to_dict())
            continue
        updates.append(record.new_image)
    if not updates:
        return
    for update in updates:
        app.log.debug(json.dumps(update, indent=4))
        helpers.send_update_message(notify_topic, update)
