from flask import Blueprint, current_app, jsonify, request
import json
import logging
import os
import uuid

from src.audit import audit_entry

base_blueprint = Blueprint('base', __name__)


@base_blueprint.route('/')
def root():
    return {'ok': True}


@base_blueprint.route('/auditlog', methods=('POST',))
def auditlog_addevent():
    """Add event to audit log

    API for client applications to add any event to the audit log.  The message
    will land in the same audit log as any auditable internal event, including
    recording the authenticated user making the call.

    Returns a json friendly message, i.e. {"message": "ok"} or details on error
    ---
    operationId: auditlog_addevent
    tags:
      - audit
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        schema:
          id: message
          required:
            - message
          properties:
            user:
              type: string
              description: user identifier, such as email address or ID
            patient:
              type: string
              description: patient identifier (if applicable)
            level:
              type: string
              description: context such as "error", default "info"
            message:
              type: string
              description: message text
    responses:
      200:
        description: successful operation
        schema:
          id: response_ok
          required:
            - message
          properties:
            message:
              type: string
              description: Result, typically "ok"
      401:
        description: if missing valid OAuth token
    security:
      - ServiceToken: []

    """
    body = request.get_json()
    if not body:
        return jsonify(message="Missing JSON data"), 400

    message = body.pop('message', None)
    level = body.pop('level', 'info')
    if not hasattr(logging, level.upper()):
        return jsonify(message="Unknown logging `level`: {level}"), 400
    if not message:
        return jsonify(message="missing required 'message' in post"), 400

    extra = {k: v for k, v in body.items()}
    audit_entry(message, level, extra)
    return jsonify(message='ok')


@base_blueprint.route('/save_data', methods=('POST',))
def save_data():
    """Write JSON to disk

    API for client applications to write JSON directly to disk.
    Intended use: front-end can capture data at any point and write
    to disk for testing & verification.

    Returns a json friendly message, i.e. {"message": "ok"} or details on error
    ---
    operationId: save_data
    tags:
      - debugging
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        schema:
          id: save_data
          required:
            - context
            - data
          properties:
            filename:
              type: string
              description: string to save file as.  UUID used by default.
                does not allow overwrites.
            context:
              type: string
              description: context such as "CQL MME calc"
            data:
              type: json
              description: json serialized data to capture
    responses:
      200:
        description: successful operation
        schema:
          id: response_ok
          required:
            - message
          properties:
            message:
              type: string
              description: Result, typically "ok"

    """
    if current_app.config["ENV"] != "development":
        return jsonify(message="Disabled on non-dev deploys"), 401
    body = request.get_json()
    if not body:
        return jsonify(message="Missing JSON data"), 400

    data = body.get('data', None)
    context = body.get('context', None)
    for item in ('data', 'context'):
        if not locals()[item]:
            return jsonify(
                message=f"missing required '{item}' in post"), 400

    filename = body.get('filename', str(uuid.uuid4()))
    location = current_app.config['DEBUG_OUTPUT_DIR']
    if not (os.path.isdir(location)):
        return jsonify(
            message="ill configured, can't find DEBUG_OUTPUT_DIR"), 400
    full_path = os.path.join(location, filename)
    if os.path.dirname(full_path) != location:
        return jsonify(
            message="no path info allowed in `filename` parameter"), 400

    if os.path.exists(full_path):
        pass  # overwrite by design on subsequent request

    with open(full_path, 'w') as fp:
        json.dump(body, fp, indent=4)

    return jsonify(message='ok', saved_file=full_path)
