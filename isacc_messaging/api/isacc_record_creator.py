from datetime import datetime

from fhirclient.models.careplan import CarePlan
from fhirclient.models.communication import Communication
from fhirclient.models.communicationrequest import CommunicationRequest
from fhirclient.models.identifier import Identifier
from fhirclient.models.patient import Patient
from flask import current_app


from isacc_messaging.api.fhir import HAPI_request


class IsaccFhirException(Exception):
    """Raised when a FHIR resource or attribute required for ISACC to operate correctly is missing"""
    pass


class IsaccTwilioError(Exception):
    """Raised when Twilio SMS are not functioning as required for ISACC"""
    pass


def first_in_bundle(bundle):
    if bundle['resourceType'] == 'Bundle' and bundle['total'] > 0:
        return bundle['entry'][0]['resource']
    return None


class IsaccRecordCreator:
    def __init__(self):
        pass

    def __create_communication_from_request(self, cr):
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

    def convert_communicationrequest_to_communication(self, cr_id=None, cr=None):
        if cr is None and cr_id is not None:
            cr = HAPI_request('GET', 'CommunicationRequest', cr_id)
        if cr is None:
            raise IsaccFhirException("No CommunicationRequest")

        cr = CommunicationRequest(cr)

        target_phone = self.get_caring_contacts_phone_number(cr.recipient[0].reference.split('/')[1])
        result = self.send_twilio_sms(message=cr.payload[0].contentString, to_phone=target_phone)

        if result.status != 'sent' and result.status != 'queued':
            raise IsaccTwilioError(f"ERROR! Message status is neither sent nor queued. It was {result.status}")
        else:
            if not cr.identifier:
                cr.identifier = []
            cr.identifier.append(Identifier({"system": "http://isacc.app/twilio-message-sid", "value": result.sid}))
            updated_cr = HAPI_request('PUT', 'CommunicationRequest', resource_id=cr.id, resource=cr.as_json())
            print(updated_cr)

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

    def get_careplan(self, patient_id):
        # result = CarePlan.where(struct={"subject": f"Patient/{patientId}",
        #                                 "category": "isacc-message-plan",
        #                                 "_sort": "-_lastUpdated"}).perform_resources(self.db.server)
        result = HAPI_request('GET', 'CarePlan', params={"subject": f"Patient/{patient_id}",
                                                         "category": "isacc-message-plan",
                                                         "_sort": "-_lastUpdated"})
        result = first_in_bundle(result)
        if result is not None:
            return CarePlan(result)
        else:
            print("no careplans found")
            return None

    def get_caring_contacts_phone_number(self, patient_id):
        pt = HAPI_request('GET', 'Patient', patient_id)
        pt = Patient(pt)
        if pt.telecom:
            for t in pt.telecom:
                if t.system == 'sms':
                    return t.value
        raise IsaccFhirException(f"Error: Patient/{pt.id} doesn't have an sms contact point on file")

    def generate_incoming_message(self, message, time: datetime = None, patient_id=None, priority=None, themes=None,
                                  twilio_sid=None):
        if priority is not None and priority != "routine" and priority != "urgent" and priority != "stat":
            raise ValueError(f"Invalid priority given: {priority}. Only routine, urgent, and stat are allowed.")

        if priority is None:
            priority = "routine"

        if patient_id is None:
            raise ValueError("Need patient ID")

        care_plan = self.get_careplan(patient_id)

        if time is None:
            time = datetime.now()

        if themes is None:
            themes = []

        m = {
            'resourceType': 'Communication',
            'identifier': [{"system": "http://isacc.app/twilio-message-sid", "value": twilio_sid}],
            'partOf': [{'reference': f'CarePlan/{care_plan.id}'}],
            'status': 'completed',
            'category': [{'coding': [{'system': 'https://isacc.app/CodeSystem/communication-type',
                                      'code': 'isacc-received-message'}]}],
            'medium': [{'coding': [{'system': 'http://terminology.hl7.org/ValueSet/v3-ParticipationMode',
                                    'code': 'SMSWRIT'}]}],
            'sent': time.astimezone().isoformat(),
            'sender': {'reference': f'Patient/{patient_id}'},
            'payload': [{'contentString': message}],
            'priority': priority,
            'extension': [
                {"url": "isacc.app/message-theme", 'valueString': t} for t in themes
            ]
        }
        c = Communication(m)
        result = HAPI_request('POST', 'Communication', resource=c.as_json())
        print(result)

    def on_twilio_message_status_update(self, values):
        message_sid = values.get('MessageSid', None)
        message_status = values.get('MessageStatus', None)

        if message_status == 'sent':
            cr = HAPI_request('GET', 'CommunicationRequest', params={
                "identifier": f"http://isacc.app/twilio-message-sid|{message_sid}"
            })
            cr = first_in_bundle(cr)
            if cr is None:
                return None

            cr = CommunicationRequest(cr)
            c = self.__create_communication_from_request(cr)
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

    def on_twilio_message_received(self, values):
        pt = HAPI_request('GET', 'Patient', params={
            'telecom': values.get('From').replace("+1", "")
        })
        pt = Patient(first_in_bundle(pt))

        self.generate_incoming_message(
            message=values.get("Body"),
            time=datetime.now(),
            twilio_sid=values.get('SmsSid'),
            patient_id=pt.id
        )

    def execute_requests(self):
        result = HAPI_request('GET', 'CommunicationRequest', params={
            "category": "isacc-scheduled-message",
            "status": "active",
            "occurrence": f"le{datetime.now().isoformat()[:16]}"
        })
        if result['resourceType'] == 'Bundle' and result['total'] > 0:
            record_creator = IsaccRecordCreator()
            for entry in result['entry']:
                cr = entry['resource']
                try:
                    result = record_creator.convert_communicationrequest_to_communication(cr=cr)
                except Exception as e:
                    print(f"CommunicationRequest/{cr['id']} could not be executed:", e)
        return ('', 200)
