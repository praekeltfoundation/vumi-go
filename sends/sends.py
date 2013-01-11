from datetime import date, timedelta, datetime
import httplib2
import urllib
import sys
import yaml
import redis
from vxpolls.manager import PollManager
from vxpolls.results import ResultManager
from vxpolls.participant import PollParticipant
from twisted.python import usage
from vumi.persist.redis_manager import RedisManager
from vumi.persist.riak_manager import RiakManager
from go.vumitools.opt_out import OptOutStore


class Sender(object):

    stdout = sys.stdout

    def __init__(self, config):
        r_config = config.get('redis', {"db": 1})
        rm_config = config.get('redis_manager', {})
        #print rm_config
        vxp_config = config.get('vxpolls', {})
        pm_prefix = vxp_config.get('prefix', 'poll_manager')
        self.r_server = self.get_redis(r_config)
        self.r_manager = RedisManager.from_config(rm_config)
        self.pm = PollManager(self.r_manager, pm_prefix)
        self.current_date = None

    def get_redis(self, config):
        return redis.Redis(**config)

    def get_current_date(self):
        if self.current_date:  # for testing
            return self.current_date
        else:
            return date.today()

    def get_last_monday(self):
        current_date = self.get_current_date()
        offset = current_date.weekday()
        monday = current_date - timedelta(days=offset)
        return monday

    def get_last_thursday(self):
        current_date = self.get_current_date()
        offset = (current_date.weekday() - 3) % 7
        thursday = current_date - timedelta(days=offset)
        return thursday

    def get_poll_number(self, birth_date):
        if isinstance(birth_date, basestring):
            birth_date = self.read_birth_date(birth_date)
        return 36 - (birth_date - self.get_last_monday()).days / 7

    def read_birth_date(self, bd_string):
        return datetime.strptime(bd_string, "%Y-%m-%d").date()

    def get_participant(self, conversation, user):
        session_data = self.r_server.hgetall("vumigo:vxpolls:session:poll-%s-%s" % (conversation, user))
        participant = PollParticipant(user, session_data)
        return participant

    def is_opted_out(self, msisdn):
        oo = self.oostore.get_opt_out('msisdn', msisdn)
        if oo:
            if str(oo.created_at.date()) >= "2012-09-01":
                return True
            else:
                return False
        else:
            return False

    def build_send_list(self, users, from_date, to_date, conversation, stage, default_message):
        HIV = 0
        Standard = 0
        Finished = 0
        params_list = []
        for u in users:
            participant = self.get_participant(conversation, u)
            if participant.labels.get('HIV_MESSAGES') \
                    and participant.get_label('REGISTRATION_DATE') >= from_date \
                    and participant.get_label('REGISTRATION_DATE') < to_date \
                    and not self.is_opted_out(u):
                poll_number = self.get_poll_number(participant.labels['BIRTH_DATE'])
                if poll_number > 88:
                    Finished += 1
                else:
                    if participant.labels.get('HIV_MESSAGES') == "1":
                        HIV += 1
                        message_type = "HIV"
                    else:
                        Standard += 1
                        message_type = "STD"

                    params = {}
                    params2 = {}
                    params['to_msisdn'] = u
                    params2['to_msisdn'] = u
                    params['from_msisdn'] = "27123456789"
                    params2['from_msisdn'] = "27123456789"

                    if stage == 0:
                        params['message'] = default_message

                    if stage == 1 or stage == 2:
                        poll_prefix = "poll-%s" % conversation
                        current_sms_poll_id = "%s_SMS_%s" % (poll_prefix, poll_number)
                        current_dict = {}
                        current_message = None
                        key = "%s_MESSAGE_%s" % (message_type, stage)
                        for q in self.pm.get(current_sms_poll_id).questions:
                            current_dict[q['label']] = q['copy']
                        current_message = current_dict[key]
                        current_message = "\n".join(current_message.split("\r\n"))
                        params['message'] = current_message[:160]

                        second_message = current_message[160:]
                        if len(second_message) >= 9:
                            params2['message'] = second_message
                        if len(second_message) > 0 and len(second_message) < 9:
                            print "ERROR: %s > WEEK %s, Length: %s > %s [%s]" % (
                                    u, poll_number, len(current_message),
                                    repr(current_message), repr(second_message))

                    params_list.append(params)
                    if params2.get('message'):
                        params_list.append(params2)

        return params_list, HIV, Standard, Finished


    def do_send(self, account, conversation, live, username, password):
        poll_prefix = "poll-%s" % conversation
        register_poll_id = "%s_0" % poll_prefix

        params_list = []

        users = self.r_server.sdiff("vumigo:vxpolls:poll:results:collections:%s:users" % (
                                         register_poll_id))
        man = RiakManager.from_config({
                "bucket_prefix": "vumigo."
                })
        self.oostore = OptOutStore(man, account)

        #self.current_date = date(2012, 10, 15)
        print "TODAY", self.get_current_date()

        PRE_DATE = "1970-01-01"
        LAST_MONDAY = str(self.get_last_monday())
        LAST_THURSDAY = str(self.get_last_thursday())

        print "LAST MONDAY", LAST_MONDAY
        print "LAST THURSDAY", LAST_THURSDAY

        FROM_DATE = min(LAST_MONDAY, LAST_THURSDAY)
        TO_DATE = max(LAST_MONDAY, LAST_THURSDAY)

        print "FROM DATE", FROM_DATE
        print "TO DATE", TO_DATE


        hello_message = "You signed up to get MAMA SMSs, every Monday & Thursday around 9am. " \
                        "To stop SMSs, send a call-me to 071 166 7783. (We won't call you back, " \
                        "SMS will just stop.)"

        hello_list = self.build_send_list(
                users=users,
                from_date=FROM_DATE,
                to_date=TO_DATE,
                conversation=conversation,
                stage=0,
                default_message=hello_message,
                )

        if LAST_MONDAY > LAST_THURSDAY:
            stage = 1
        else:
            stage = 2

        print "STAGE", stage

        info_list = self.build_send_list(
                users=users,
                from_date=PRE_DATE,
                to_date=TO_DATE,
                conversation=conversation,
                stage=stage,
                default_message=None,
                )

        #for h in hello_list[0]:
            #print h

        #for i in info_list[0]:
            #print i

        print "NEW", len(hello_list[0])
        print "NEW HIV", hello_list[1]
        print "NEW Standard", hello_list[2]
        print "HIV", info_list[1]
        print "Standard", info_list[2]
        print "Finished", info_list[3]
        print "TOTAL", info_list[1] + info_list[2] + info_list[3]

        #return

        url = "http://vumi.praekeltfoundation.org/api/v1/sms/send.json"

        #hello_list = ([{"to_msisdn": "27763805186", "from_msisdn": "27123456789", "message": "mama hello"}], 1, 0)
        #info_list = ([{"to_msisdn": "27763805186", "from_msisdn": "27123456789", "message": "mama info"}], 1, 0)

        http = httplib2.Http()
        http.add_credentials(username, password)

        for params in hello_list[0]:
            if str(live) == "1":
                response = http.request(url, "POST", urllib.urlencode(params))
                print response
            else:
                print len(params['message']), params

        for params in info_list[0]:
            if str(live) == "1":
                response = http.request(url, "POST", urllib.urlencode(params))
                print response
            else:
                print len(params['message']), params

        print "NEW", len(hello_list[0])
        print "NEW HIV", hello_list[1]
        print "NEW Standard", hello_list[2]
        print "HIV", info_list[1]
        print "Standard", info_list[2]
        print "Finished", info_list[3]
        print "TOTAL", info_list[1] + info_list[2] + info_list[3]


class Options(usage.Options):

    optParameters = [
        ["config", None, None, "The config file to read"],
        ["account", None, None, "The vumi-go account key"],
        ["conversation",None, None, "The multi-survey conversation to process"],
        ["username", None, None, "The vumi.praekeltfoundation.org username"],
        ["password", None, None, "The vumi.praekeltfoundation.org password"],
        ["live", None, None, "Dummy run (0) or actually do the send (1)"]
    ]

    def postOptions(self):
        if not (
                self['config'] and
                self['account'] and
                self['conversation'] and
                self['live'] and
                self['username'] and
                self['password']
                ):
            raise usage.UsageError(
                "Please specify --config, --account, --conversation, "\
                        "--live, --username and --password")


if __name__ == '__main__':
    options = Options()
    try:
        options.parseOptions()
    except usage.UsageError, errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)

    config_file = options['config']
    config = yaml.safe_load(open(config_file, 'r'))

    sender = Sender(config)
    sender.do_send(
            account=options['account'],
            conversation=options['conversation'],
            live=options['live'],
            username=options['username'],
            password=options['password'],
            )
