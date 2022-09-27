ISACC Messaging Service
===================
Backend service facilitating ISACC messaging needs.  Monitors the configured
FHIR store for CommunicationRequests and generates Communications including
firing SMS via contained APIs.

Development
-----------
To start the application follow the below steps in the checkout root

Copy default environment variable file and modify as necessary

    cp messaging.env.default messaging.env

Build the docker image. Should only be necessary on first run or if dependencies change.

    docker-compose build

Start the container in detached mode

    docker-compose up --detach

Read application logs

    docker-compose logs --follow


Test
----
Without a ``setup.py`` to install, invoke as follows from the root directory to
automatically include the current directory in ``PYTHONPATH``

    python -m pytest tests

License
-------
BSD
