"""manage.py twilio_test --to 0771234567 [--whatsapp]

Sends one test message through Twilio to a number you type (deploy/configure-twilio.sh runs it after saving the
settings). It goes to that number only -- never to a respondent -- and is not counted against the daily caps."""

from django.core.management.base import BaseCommand, CommandError

from apps.messaging import twilio_client as tw
from apps.messaging.services import whatsapp_digits


class Command(BaseCommand):
    help = "Send one test SMS (or WhatsApp invitation template) through Twilio to the number given."

    def add_arguments(self, parser):
        parser.add_argument("--to", required=True, help="A mobile number, e.g. 0771234567 or +263771234567.")
        parser.add_argument("--whatsapp", action="store_true", help="Send the WhatsApp invitation template instead of an SMS.")

    def handle(self, *args, to, whatsapp=False, **options):
        digits = whatsapp_digits(to)
        if not digits:
            raise CommandError("That is not a mobile number.")
        try:
            if whatsapp:
                from django.conf import settings

                if not tw.whatsapp_configured():
                    raise CommandError("WhatsApp is not set up: the sender and the invitation template id are needed.")
                result = tw.send_whatsapp(digits, settings.TWILIO_WA_CONTENT_INVITATION.strip(), {
                    1: "Test organisation", 2: f"https://{settings.APP_DOMAIN}/", 3: "1 January 2027", 4: "TEST1234",
                })
            else:
                if not tw.sms_configured():
                    raise CommandError("SMS is not set up: the Account SID, Auth Token and sender are needed.")
                result = tw.send_sms(digits, "ABF-FST portal test: SMS from research.agribizframework.com works.", delays=())
        except tw.TwilioError as exc:
            raise CommandError(f"Twilio refused the message: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"Sent to {tw.mask(digits)} (Twilio status: {result.get('status')}, id {result.get('sid')})."))
