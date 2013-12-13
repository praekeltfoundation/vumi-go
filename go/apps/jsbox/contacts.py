# -*- test-case-name: go.apps.jsbox.tests.test_contacts -*-
# -*- coding: utf-8 -*-

import hashlib
import uuid
import json

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi import log
from vumi.application.sandbox import SandboxResource, SandboxError
from vumi.persist.txredis_manager import TxRedisManager

from go.vumitools.contact import (
    Contact, ContactStore, ContactError, ContactNotFoundError)


class ContactsResource(SandboxResource):
    """
    Sandbox resource for accessing, creating and modifying contacts for
    a Go application.

    See :class:`go.vumitools.contact.Contact` for a look at the Contact model
    and its fields.
    """

    # FIXME: Put these in the puppet config, wherever it is.
    MAX_BATCH_SIZE = 2
    SEARCH_CACHE_EXPIRE = 300

    @inlineCallbacks
    def setup(self):
        redis_config = self.config.get('redis_manager', {})
        self.redis = yield TxRedisManager.from_config(redis_config)

    def teardown(self):
        return self.redis.close_manager()

    def _contact_store_for_api(self, api):
        return self.app_worker.user_api_for_api(api).contact_store

    def _parse_get(self, command):
        if not isinstance(command.get('addr'), unicode):
            raise SandboxError(
                "'addr' needs to be specified and be a unicode string")

        if 'delivery_class' not in command:
            if 'delivery_class' in self.config:
                command['delivery_class'] = self.config['delivery_class']

        if not isinstance(command.get('delivery_class'), unicode):
            raise SandboxError(
                "'delivery_class' needs to be specified and be a unicode "
                "string")

    @inlineCallbacks
    def handle_get(self, api, command):
        """
        Accepts a delivery class and address and returns a contact's data, as
        well as the success flag of the operation (can be ``true`` or
        ``false``).

        Command fields:
            - ``delivery_class``: the type of channel used for the passed in
              address. Can be one of the following types: ``sms``, ``ussd``,
              ``twitter``, ``gtalk``
            - ``addr``: The address to use to lookup of the contact. For
              example, if ``sms`` was the delivery class, the address would
              look something like ``+27731112233``

        Success reply fields:
            - ``success``: set to ``true``
            - ``contact``: An object containing the contact's data. Looks
              something like this:

            .. code-block:: javascript

                {
                    'key': 'f953710a2472447591bd59e906dc2c26',
                    'surname': 'Person',
                    'user_account': 'test-0-user',
                    'bbm_pin': null,
                    'msisdn': '+27831234567',
                    'created_at': '2013-04-24 14:01:41.803693',
                    'gtalk_id': null,
                    'dob': null,
                    'groups': ['group-a', 'group-b'],
                    'facebook_id': null,
                    '$VERSION': null,
                    'twitter_handle': null,
                    'email_address': null,
                    'name': 'A Random'
                }

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'contacts.get',
                {delivery_class: 'sms', addr: '+27731112233'},
                function(reply) { api.log_info(reply.contact.name); });
        """
        try:
            self._parse_get(command)

            contact = yield self._contact_store_for_api(api).contact_for_addr(
                command['delivery_class'],
                command['addr'],
                create=False)
        except (SandboxError, ContactError) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        if contact is None:
            returnValue(self.reply(
                command, success=False, reason="Contact not found"))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))

    @inlineCallbacks
    def handle_get_or_create(self, api, command):
        """
        Similar to :func:`handle_get`, but creates the contact if it does
        not yet exist.

        Success reply fields:
            - ``success``: set to ``true``
            - ``contact``: An object containing the contact's data
            - ``created``: ``true`` if a new contact was created, otherwise
              ``false``

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure
        """
        try:
            self._parse_get(command)
            contact_store = self._contact_store_for_api(api)
            contact = yield contact_store.contact_for_addr(
                command['delivery_class'],
                command['addr'],
                create=False)
            created = False
        except ContactNotFoundError:
            contact = yield contact_store.new_contact_for_addr(
                command['delivery_class'],
                command['addr'])
            created = True
        except (SandboxError, ContactError) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            created=created,
            contact=contact.get_data()))

    @staticmethod
    def pick_fields(collection, *fields):
        return dict((k, collection[k]) for k in fields if k in collection)

    @inlineCallbacks
    def handle_update(self, api, command):
        """
        Updates the given fields of an existing contact.

        **Note**: All subfields of a Dynamic field such as ``extra`` and
        ``subscription`` are overwritten if specified as one of the fields to
        be updated.

        Command fields:
            - ``key``: The contacts key
            - ``fields``: The contact fields to be updated

        Success reply fields:
            - ``success``: set to ``true``
            - ``contact``: An object containing the contact's data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'contacts.update', {
                     key: 'f953710a2472447591bd59e906dc2c26',
                     fields: {surname: 'Jones', extra: {location: 'CPT'}}},
                function(reply) { api.log_info(reply.success); });
        """
        try:
            if not isinstance(command.get('key'), unicode):
                raise SandboxError(
                    "'key' needs to be specified and be a unicode string")

            if not isinstance(command.get('fields'), dict):
                raise SandboxError(
                    "'fields' needs to be specified and be a dict of field "
                    "name-values pairs")

            store = self._contact_store_for_api(api)
            fields = self.pick_fields(
                command['fields'], *Contact.field_descriptors)
            contact = yield store.update_contact(command['key'], **fields)
        except (SandboxError, ContactError) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))

    @inlineCallbacks
    def _update_dynamic_fields(self, dynamic_field_name, api, command):
        try:
            if not isinstance(command.get('key'), unicode):
                raise SandboxError(
                    "'key' needs to be specified and be a unicode "
                    "string")

            if not isinstance(command.get('fields'), dict):
                raise SandboxError(
                    "'fields' needs to be specified and be a dict of field "
                    "name-values pairs")

            fields = command['fields']
            if any(not isinstance(k, unicode) for k in fields.keys()):
                raise SandboxError("All field names need to be unicode")

            if any(not isinstance(v, unicode) for v in fields.values()):
                raise SandboxError("All field values need to be unicode")

            store = self._contact_store_for_api(api)
            contact = yield store.get_contact_by_key(command['key'])

            dynamic_field = getattr(contact, dynamic_field_name)
            for k, v in fields.iteritems():
                dynamic_field[k] = v

            yield contact.save()
        except (SandboxError, ContactError) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))

    def handle_update_extras(self, api, command):
        """
        Updates subfields of an existing contact's ``extra`` field.

        Command field:
            - ``key``: The contact's key
            - ``fields``: The extra fields to be updated

        Success reply fields:
            - ``success``: set to ``true``
            - ``contact``: An object containing the contact's data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'contacts.update_extras', {
                    key: f953710a2472447591bd59e906dc2c26',
                    fields: {location: 'CPT', beer: 'Whale Tail Ale'}},
                function(reply) { api.log_info(reply.success); });
        """
        return self._update_dynamic_fields('extra', api, command)

    def handle_update_subscriptions(self, api, command):
        """
        Updates subfields of an existing contact's ``subscription`` field.

        Command field:
            - ``key``: The contact's key
            - ``fields``: The subscription fields to be updated

        Success reply fields:
            - ``success``: set to ``true``
            - ``contact``: An object containing the contact's data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'contacts.update_subscriptions', {
                    key: f953710a2472447591bd59e906dc2c26',
                    fields: {a: 'one', b: 'two'}},
                function(reply) { api.log_info(reply.success); });
        """
        return self._update_dynamic_fields('subscription', api, command)

    @inlineCallbacks
    def handle_new(self, api, command):
        """
        Creates a new contacts with the given fields of an existing contact.

        Command fields:
            - ``contact``: The contact data to initialise the new contact with.

        Success reply fields:
            - ``success``: set to ``true``
            - ``contact``: An object containing the contact's data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'contacts.new',
                {contact: {surname: 'Jones', extra: {location: 'CPT'}}},
                function(reply) { api.log_info(reply.success); });
        """
        try:
            if not isinstance(command.get('contact'), dict):
                raise SandboxError(
                    "'contact' needs to be specified and be a dict of field "
                    "name-value pairs")

            fields = self.pick_fields(command['contact'],
                                      *Contact.field_descriptors)
            contact_store = self._contact_store_for_api(api)
            contact = yield contact_store.new_contact(**fields)
        except (SandboxError, ContactError) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))

    @inlineCallbacks
    def handle_save(self, api, command):
        """
        Saves a contact's data, overwriting the contact's previous data. Use
        with care. This operation only works for existing contacts. For
        creating new contacts, use :func:`handle_new`.

        Command fields:
            - ``contact``: The contact's data. **Note**: ``key`` must be a
              field in the contact data in order identify the contact.

        Success reply fields:
            - ``success``: set to ``true``
            - ``contact``: An object containing the contact's data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'contacts.save', {
                    contact: {
                        'key': 'f953710a2472447591bd59e906dc2c26',
                        'surname': 'Person',
                        'user_account': 'test-0-user',
                        'msisdn': '+27831234567',
                        'groups': ['group-a', 'group-b'],
                        'name': 'A Random'
                    }
                },
                function(reply) { api.log_info(reply.success); });
        """
        try:
            if not isinstance(command.get('contact'), dict):
                raise SandboxError(
                    "'contact' needs to be specified and be a dict of field "
                    "name-value pairs")

            fields = command['contact']
            if not isinstance(fields.get('key'), unicode):
                raise SandboxError(
                    "'key' needs to be specified as a field in 'contact' and "
                    "be a unicode string")

            # These are foreign keys.
            groups = fields.pop('groups', [])

            key = fields.pop('key')
            contact_store = self._contact_store_for_api(api)

            # raise an exception if the contact does not exist
            yield contact_store.get_contact_by_key(key)

            contact = contact_store.contacts(
                key,
                user_account=contact_store.user_account_key,
                **ContactStore.settable_contact_fields(**fields))

            # since we are basically creating a 'new' contact with the same
            # key, we can be sure that the old groups were removed
            for group in groups:
                contact.add_to_group(group)

            yield contact.save()
        except (SandboxError, ContactError) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            contact=contact.get_data()))

    def _token(self, request_id, page):
        """
        Constructs an opaque token which the user can use for paging
        through results. Since the token is opaque, we can modify our
        search implementation without having to change or
        break the JS Sandbox API.

        For example, if move to over to using a full Riak search
        backend, we could construct a token as follows:

           token := "{query}:{start}:{count}"

        Anyhow, In the current implementation, ``request_id`` is a
        unique ID identifying a 'contact.search' request
        performed by the user. Success calls to ``contact.search``
        with the same query string and nextToken will share the
        same request_id.

        ``page`` is a key used to retrieve the next batch of
        of results.

        """
        return "%s:%s" % (request_id, page)

    def _token_parse(self, token):
        """Parse request_id from token"""
        try:
            request_id, page = token.split(':')
            return (request_id, int(page),)
        except (Exception, ValueError,) as e:
            e.args = ("Parameter value for 'nextToken' is invalid: %s"
                      % e.args[0])
            raise e

    def _search_result_key(self, api, request_id, query):
        """
        Construct a unique key for caching search results

        We include both the request_id and the query in the key.

        This acts as a way of forcing the user to a pass a ``nextToken``
        and ``query`` that are related to one another.
        """
        prefix = "search:contacts"
        return ("%s:%s:%s:%s" % (prefix,
                                 api.sandbox_id,
                                 request_id,
                                 hashlib.sha1(query).hexdigest()))

    def make_batches(self, keys, size):
        cache = {}
        batches = [keys[i:i + size] for i in range(0, len(keys), size)]
        for i, batch in [(i, b) for i, b in
                         zip(range(0, len(batches)), batches)]:
            cache[str(i)] = json.dumps(batch)
        return cache

    @inlineCallbacks
    def _cache_search_result(self, api, request_id, query, keys):
        """
        Caches search result keys and returns the tuple (KEYS, MORE, PAGE).

        KEYS is a list of keys for contacts we can send to the user right now.
        MORE is a boolean indicating that there are more results available.
        PAGE is the key used to lookup the next batch of results.

        ``request_id`` and PAGE are used to form the token which will be
        included in the response, iff MORE is true.
        """
        redis_key = self._search_result_key(api, request_id, query)
        size = self.MAX_BATCH_SIZE
        keys, remaining = (keys[:size], keys[size:],)

        if remaining:
            batches = self.make_batches(remaining, self.MAX_BATCH_SIZE)
            for batch_key, batch_value in batches.items():
                yield self.redis.hset(redis_key, batch_key, batch_value)
            yield self.redis.expire(redis_key, self.SEARCH_CACHE_EXPIRE)

        returnValue((keys, len(remaining) > 0, 0))

    @inlineCallbacks
    def _next_batch_of_keys(self, api, request_id, page, query):
        """
        Similarly to ``_cache_search_result`` this function returns
        a 3-tuple with the updated paging state.

        Uses ``page`` to fetch the next batch of contact keys.

        """
        redis_key = self._search_result_key(api, request_id, query)

        keys = yield self.redis.hget(redis_key, str(page))
        if keys:
            keys = json.loads(keys)
            more = yield self.redis.hexists(redis_key, str(page + 1))
            more = more == 1
            if more:
                yield self.redis.expire(redis_key, self.SEARCH_CACHE_EXPIRE)
        else:
            more = False
            keys = []

        returnValue((keys, more, page + 1))

    @inlineCallbacks
    def handle_search(self, api, command):
        """
        Search for contacts

        Paging is implemented using the iterator pattern. The iterator is
        represented as an opaque token that hides the current iteration
        state and paging mechanism.

        Command fields:
            - ``query``: The Lucene search query to perform.
            - ``nextToken``: Informs Go to return the next batch of contacts.
                             This field must correspond to the ``nextToken``
                             value returned by the previous 'contact.search'
                             call.

        Success reply fields:
            - ``success``: set to ``true``
            - ``contacts``: A list of dictionaries with contact information.
            - ``nextToken``: If present, signifies that there are more
                             results available. To fetch the next batch of
                             results, you should call 'contact.search' again
                             with the same query and this token.

        Note: If no matches are found ``contacts`` will be an empty list.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Examples:

        Searching on a single contact field:

        .. code-block:: javascript

            api.request(
                'contacts.search', {
                     query: 'name:"My Name"',
                },
                function(reply) { api.log_info(reply.contacts); });

        Paging over search results:

        .. code-block:: javascript

           // basic paging search helper
           function _search(query, nextToken, handler_func) {
               cmd = {
                   query: query,
               };
               if (nextToken) {
                   cmd['nextToken'] = nextToken;
               }
               api.request(
                   'contacts.search', cmd,
                    function(reply) {
                        if (handler_func(reply) && reply.nextToken) {
                             _search(query, reply.nextToken, handler_func);
                        }
                   });
           }

           // adaptor with a friendlier interface
           function search(query, handler_func) {
               _search(query, false, handler_func)
           }

           // Search for contacts, and process results
           // as they are delivered
           search('msisdn:"+27*"',
                  function (reply) {
                      api.log_info(reply.contacts);
                      // we want to retrieve all pages
                      return true;
                  });

           // NOTE: These helpers should really go into the JS Sandbox.
        """
        try:
            contact_store = self._contact_store_for_api(api)
            if 'nextToken' in command and command['nextToken'] is not None:
                # user is requesting more results
                request_id, page = self._token_parse(command['nextToken'])
                keys, more, page = yield self._next_batch_of_keys(
                    api,
                    request_id,
                    page,
                    command['query']
                )
            else:
                request_id = str(uuid.uuid4())
                keys = yield contact_store.contacts.raw_search(
                    command['query']).get_keys()
                keys, more, page = yield self._cache_search_result(
                    api,
                    request_id,
                    command['query'],
                    keys
                )

            contacts = []
            for contact_bunch in contact_store.contacts.load_all_bunches(keys):
                contacts.extend((yield contact_bunch))

        except (SandboxError,) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))
        except (Exception,) as e:
            # NOTE: Hello Riakasaurus, you raise horribly plain exceptions on
            #       a MapReduce error.
            if 'MapReduce' not in str(e):
                raise
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        extra_fields = {}
        if more:
            extra_fields['nextToken'] = self._token(request_id, page)

        returnValue(self.reply(
            command,
            success=True,
            contacts=[contact.get_data() for contact in contacts],
            **extra_fields))


class GroupsResource(SandboxResource):
    """
    Sandbox resource for accessing, creating and modifying groups for
    a Go application.

    See :class:`go.vumitools.contact.ContactGroup` for a look at the Contact
    model and its fields.
    """

    def _contact_store_for_api(self, api):
        return self.app_worker.user_api_for_api(api).contact_store

    @inlineCallbacks
    def handle_search(self, api, command):
        """
        Search for groups

        Command fields:
            - ``query``: The Lucene search query to perform.

        Success reply fields:
            - ``success``: set to ``true``
            - ``groups``: An list of dictionaries with group information.

        Note:   If no matches are found ``groups`` will be an empty list.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'groups.search', {
                     query: 'name:"My Group"',
                },
                function(reply) { api.log_info(reply.groups); });
        """
        try:
            contact_store = self._contact_store_for_api(api)
            keys = yield contact_store.groups.raw_search(
                command['query']).get_keys()
            groups = []
            for group_bunch in contact_store.groups.load_all_bunches(keys):
                groups.extend((yield group_bunch))

        except (SandboxError,) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))
        except (Exception,) as e:
            # NOTE: Hello Riakasaurus, you raise horribly plain exceptions on
            #       a MapReduce error.
            if 'MapReduce' not in str(e):
                raise
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command,
            success=True,
            groups=[group.get_data() for group in groups]))

    @inlineCallbacks
    def handle_get(self, api, command):
        """
        Get a group by its key

        Command fields:
            - ``key``: The key of the group to retrieve

        Success reply fields:
            - ``success``: set to ``true``
            - ``group``: A dictionary with the group's data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'groups.get', {
                     key: 'a-key',
                },
                function(reply) { api.log_info(reply.group); });
        """
        try:
            contact_store = self._contact_store_for_api(api)
            group = yield contact_store.get_group(command['key'])
        except (SandboxError,) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        if group is None:
            returnValue(self.reply(
                command, success=False, reason='Group not found'))

        returnValue(self.reply(
            command,
            success=True,
            group=group.get_data()))

    @inlineCallbacks
    def handle_get_by_name(self, api, command):
        """
        Get a group by its name

        Command fields:
            - ``name``: The key of the group to retrieve

        Success reply fields:
            - ``success``: set to ``true``
            - ``group``: A dictionary with the group's data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Note:   If more than 1 matching groups are found a Failure reply is
                returned.

        Example:

        .. code-block:: javascript

            api.request(
                'groups.get_by_name', {
                     name: 'My Group',
                },
                function(reply) { api.log_info(reply.group); });
        """
        try:
            contact_store = self._contact_store_for_api(api)
            keys = yield contact_store.groups.search(
                name=command['name']).get_keys()
        except (SandboxError,) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))
        except (Exception,) as e:
            # NOTE: Hello Riakasaurus, you raise horribly plain exceptions on
            #       a MapReduce error.
            if 'MapReduce' not in str(e):
                raise
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        if not keys:
            returnValue(self.reply(
                command, success=False, reason='Group not found'))

        if len(keys) != 1:
            returnValue(self.reply(
                command, success=False, reason='Multiple groups found'))

        [key] = keys
        group = yield contact_store.get_group(key)
        returnValue(self.reply(
            command, success=True, group=group.get_data()))

    @inlineCallbacks
    def handle_get_or_create_by_name(self, api, command):
        """
        Get or create a group by its name

        Command fields:
            - ``name``: The name of the group to get or create

        Success reply fields:
            - ``success``: set to ``true``
            - ``group``: A dictionary with the group's data.
            - ``created``: A boolean, ``True`` if created, ``False`` if not.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'groups.get_or_create_by_name', {
                     name: 'My Group',
                },
                function(reply) { api.log_info(reply.group); });
        """
        try:
            contact_store = self._contact_store_for_api(api)
            keys = yield contact_store.groups.search(
                name=command['name']).get_keys()
        except (SandboxError,) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))
        except (Exception,) as e:
            # NOTE: Hello Riakasaurus, you raise horribly plain exceptions on
            #       a MapReduce error.
            if 'MapReduce' not in str(e):
                raise
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        if not keys:
            group = yield contact_store.new_group(command['name'])
            returnValue(self.reply(
                command, success=True, created=True, group=group.get_data()))

        if len(keys) != 1:
            returnValue(self.reply(
                command, success=False, reason='Multiple groups found'))

        [key] = keys
        group = yield contact_store.get_group(key)
        returnValue(self.reply(
            command, success=True, created=False, group=group.get_data()))

    @inlineCallbacks
    def handle_update(self, api, command):
        """
        Update a group's name or query.

        Command fields:
            - ``key``: The key of the group to retrieve
            - ``name``: The new name
            - ``query``: The query to store, defaults to ``None``.

        Note:   If a ``query`` is provided the group is treated as a
                "smart" group.

        Success reply fields:
            - ``success``: set to ``true``
            - ``group``: A dictionary with the group's updated data.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'groups.update', {
                     key: 'a-key',
                     name: 'My New Group',
                     query: 'name:foo*'
                },
                function(reply) { api.log_info(reply.group); });
        """
        try:
            contact_store = self._contact_store_for_api(api)
            group = yield contact_store.get_group(command['key'])
        except (SandboxError,) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        if group is None:
            returnValue(self.reply(
                command, success=False, reason='Group not found'))

        group.name = command['name']
        group.query = command.get('query', None)
        yield group.save()

        returnValue(self.reply(
            command,
            success=True,
            group=group.get_data()))

    @inlineCallbacks
    def handle_count_members(self, api, command):
        """
        Count the number of members in a group.

        Command fields:
            - ``key``: The key of the group to retrieve

        Success reply fields:
            - ``success``: set to ``true``
            - ``group``: A dictionary with the group's data.
            - ``count``: The number of members in this group.

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'groups.count_members', {
                     key: 'a-key'
                },
                function(reply) { api.log_info(reply.group); });
        """
        try:
            contact_store = self._contact_store_for_api(api)
            group = yield contact_store.get_group(command['key'])
        except (SandboxError,) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        member_count = yield contact_store.count_contacts_for_group(group)
        returnValue(self.reply(
            command, success=True, count=member_count, group=group.get_data()))

    @inlineCallbacks
    def handle_list(self, api, command):
        """
        List all known groups

        Command fields: None

        Success reply fields:
            - ``success``: set to ``true``
            - ``groups``: A list of dictionaries with group data

        Failure reply fields:
            - ``success``: set to ``false``
            - ``reason``: Reason for the failure

        Example:

        .. code-block:: javascript

            api.request(
                'groups.list', {},
                function(reply) { api.log_info(reply.groups); });
        """
        try:
            contact_store = self._contact_store_for_api(api)
            groups = yield contact_store.list_groups()
        except (SandboxError,) as e:
            log.warning(str(e))
            returnValue(self.reply(command, success=False, reason=unicode(e)))

        returnValue(self.reply(
            command, success=True,
            groups=[group.get_data() for group in groups]))
