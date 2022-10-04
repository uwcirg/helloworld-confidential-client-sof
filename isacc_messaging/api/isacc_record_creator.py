from datetime import datetime

from fhirclient.models.careplan import CarePlan
from fhirclient.models.communication import Communication
from fhirclient.models.communicationrequest import CommunicationRequest
from fhirclient.models.identifier import Identifier
from fhirclient.models.patient import Patient
from flask import current_app
from twilio.base.exceptions import TwilioRestException

from isacc_messaging.api.fhir import HAPI_request


class IsaccRecordCreator:
    def __init__(self):
        pass

    def __createCommunicationFromRequest(self, cr):
        return {
            "resourceType": "Communication",
            "basedOn": [{"reference": f"CommunicationRequest/{cr.id}"}],
            "partOf": [{"reference": f"{cr.basedOn[0].reference}"}],
            "category": [{
                "coding": [{
                    "system": "https://isacc.app/CodeSystem/communication-type",
                    "code": "isacc-auto-sent-message"
                }]
            }],

            "payload": [p.as_json() for p in cr.payload],
            "sent": datetime.now().astimezone().isoformat(),
            "recipient": [r.as_json() for r in cr.recipient],
            "medium": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/ValueSet/v3-ParticipationMode",
                    "code": "SMSWRIT"
                }]
            }],
            "status": "completed"
        }

    def convertCommunicationToRequest(self, cr_id):
        # cr = CommunicationRequest.read(cr_id, self.db.server)
        cr = HAPI_request('GET', 'CommunicationRequest', cr_id)
        cr = CommunicationRequest(cr)

        target_phone = self.getCaringContactsPhoneNumber(cr.recipient[0].reference.split('/')[1])
        try:
            result = self.send_twilio_sms(message=cr.payload[0].contentString, to_phone=target_phone)
        except TwilioRestException as exception:
            print("Error! Message will not be sent.", exception)
            return None
        if result.status != 'sent' and result.status != 'queued':
            print("ERROR! Message status is neither sent nor queued. It was", result.status)
            return None
        else:
            if not cr.identifier:
                cr.identifier = []
            cr.identifier.append(Identifier({"system": "http://isacc.app/twilio-message-sid", "value": result.sid}))
            updated_cr = HAPI_request('PUT', 'CommunicationRequest', resource_id=cr.id, resource=cr.as_json())
            print(updated_cr)
            # print(cr.update(self.db.server))
            return updated_cr

    def send_twilio_sms(self, message, to_phone, from_phone='+12535183975'):
        from twilio.rest import Client
        account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
        auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')

        webhook_callback = current_app.config.get('WEBHOOK_CALLBACK')

        client = Client(account_sid, auth_token)

        message = client.messages.create(
            body=message,
            from_=from_phone,
            to=to_phone,
            status_callback=webhook_callback + '/MessageStatus'
        )

        print("Message created:", message)
        return message

    def getCareplan(self, patientId):
        # result = CarePlan.where(struct={"subject": f"Patient/{patientId}",
        #                                 "category": "isacc-message-plan",
        #                                 "_sort": "-_lastUpdated"}).perform_resources(self.db.server)
        result = HAPI_request('GET', 'CarePlan', params={"subject": f"Patient/{patientId}",
                                                         "category": "isacc-message-plan",
                                                         "_sort": "-_lastUpdated"})
        if result is not None and result['total'] > 0:
            return CarePlan(result['entry'][0]['resource'])
        else:
            print("no careplans found")
            return None

    def getCaringContactsPhoneNumber(self, patientId):
        pt = HAPI_request('GET', 'Patient', patientId)
        pt = Patient(pt)
        for t in pt.telecom:
            if t.system == 'sms':
                return t.value
        print("Error: Patient doesn't have an sms contact point on file")
        return None

    def generateIncomingMessage(self, message, time: datetime = None, patientId=None, priority=None, themes=None, twilioSid=None):
        if priority is not None and priority != "routine" and priority != "urgent" and priority != "stat":
            print(f"Invalid priority given: {priority}. Only routine, urgent, and stat are allowed.")
            return

        if priority is None:
            priority = "routine"

        if patientId is None:
            patientId = "2cda5aad-e409-4070-9a15-e1c35c46ed5a"  # Geoffrey Abbott

        carePlan = self.getCareplan(patientId)

        if time is None:
            time = datetime.now()

        if themes is None:
            themes = []

        m = {
            'resourceType': 'Communication',
            'identifier': [{"system": "http://isacc.app/twilio-message-sid", "value": twilioSid}],
            'partOf': [{'reference': f'CarePlan/{carePlan.id}'}],
            'status': 'completed',
            'category': [{'coding': [{'system': 'https://isacc.app/CodeSystem/communication-type',
                                      'code': 'isacc-received-message'}]}],
            'medium': [{'coding': [{'system': 'http://terminology.hl7.org/ValueSet/v3-ParticipationMode',
                                    'code': 'SMSWRIT'}]}],
            'sent': time.astimezone().isoformat(),
            'sender': {'reference': f'Patient/{patientId}'},
            'payload': [{'contentString': message}],
            'priority': priority,
            'extension': [
                {"url": "isacc.app/message-theme", 'valueString': t} for t in themes
            ]
        }
        c = Communication(m)
        result = HAPI_request('POST', 'Communication', resource=c.as_json())
        # result = c.create(self.db.server)
        print(result)


    def onTwilioMessageStatusUpdate(self, values):
        message_sid = values.get('MessageSid', None)
        message_status = values.get('MessageStatus', None)

        if message_status == 'sent':
            cr = HAPI_request('GET', 'CommunicationRequest', params={
                "identifier": f"http://isacc.app/twilio-message-sid|{message_sid}"
            })
            if cr['resourceType'] == 'Bundle':
                if cr['total'] == 0:
                    return None
                cr = cr['entry'][0]['resource']

            cr = CommunicationRequest(cr)
            c = self.__createCommunicationFromRequest(cr)
            c = Communication(c)

            print("Creating resource: ")
            print(c.as_json())
            # result = c.create(self.db.server)
            result = HAPI_request('POST', 'Communication', resource=c.as_json())
            print("Created resource: ")
            print(result)

            cr.status = "completed"
            updated_cr = HAPI_request('PUT', 'CommunicationRequest', resource_id=cr.id, resource=cr.as_json())
            print("Updated request object with status complete: ")
            print(updated_cr)
            # print(cr.update(self.db.server))
            print()

            return result

    def onTwilioMessageReceived(self, values):
        pt = HAPI_request('GET', 'Patient', params={
            'telecom': values.get('From').replace("+1", "")
        })
        if pt['resourceType'] == 'Bundle' and pt['total'] > 0:
            pt = Patient(pt['entry'][0]['resource'])

        self.generateIncomingMessage(
            message=values.get("Body"),
            time=datetime.now(),
            twilioSid=values.get('SmsSid'),
            patientId=pt.id
        )
        pass

