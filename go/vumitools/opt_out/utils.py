from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.config import Config, ConfigBool, ConfigList

from go.vumitools.utils import MessageMetadataHelper


class OptOutHelperConfig(Config):
    case_sensitive = ConfigBool(
        "Whether case sensitivity should be enforced when checking message "
        "content for opt outs",
        default=False)

    keywords = ConfigList(
        "List of the keywords which count as opt outs",
        default=())


class OptOutHelper(object):
    def __init__(self, vumi_api, config):
        self.vumi_api = vumi_api
        self.config = OptOutHelperConfig(config)
        self.optout_keywords = set([
            self.casing(word) for word in self.config.keywords])

    def casing(self, word):
        if not self.config.case_sensitive:
            return word.lower()
        return word

    def keyword(self, message):
        keyword = (message['content'] or '').strip()
        return self.casing(keyword)

    @inlineCallbacks
    def _optout_disabled(self, account, message):
        msg_mdh = MessageMetadataHelper(self.vumi_api, message)

        if account.disable_optouts:
            returnValue(True)
        elif msg_mdh.tag is not None:
            tagpool_metadata = yield msg_mdh.get_tagpool_metadata()
            returnValue(tagpool_metadata.get('disable_global_opt_out', False))
        else:
            returnValue(False)

    @inlineCallbacks
    def _is_optout(self, account, message):
        if (yield self._optout_disabled(account, message)):
            returnValue(False)
        else:
            returnValue(self.keyword(message) in self.optout_keywords)

    @inlineCallbacks
    def process_message(self, account, message):
        helper_metadata = message['helper_metadata']

        if 'optout' not in helper_metadata:
            optout_metadata = {'optout': False}
            helper_metadata['optout'] = optout_metadata

            if (yield self._is_optout(account, message)):
                optout_metadata['optout'] = True
                optout_metadata['optout_keyword'] = self.keyword(message)

        returnValue(message)

    @staticmethod
    def is_optout_message(message):
        return message['helper_metadata'].get('optout', {}).get('optout')
