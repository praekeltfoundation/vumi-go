from datetime import datetime

from vumi.persist.model import Model
from vumi.persist.fields import (
   Integer, Unicode, Timestamp, ManyToMany, Json,
                                    Boolean)


class UserTagPermissionVNone(Model):
    """A description of a tag a user account is allowed access to."""
    # key is uuid
    tagpool = Unicode(max_length=255)
    max_keys = Integer(null=True)


class UserAppPermissionVNone(Model):
    """An application that provides a certain conversation_type"""
    application = Unicode(max_length=255)


class UserAccountVNone(Model):
    """A user account."""
    # key is uuid
    username = Unicode(max_length=255)
    # TODO: tagpools can be made OneToMany once vumi.persist.fields
    #       gains a OneToMany field
    tagpools = ManyToMany(UserTagPermissionVNone)
    applications = ManyToMany(UserAppPermissionVNone)
    created_at = Timestamp(default=datetime.utcnow)
    event_handler_config = Json(null=True)
    msisdn = Unicode(max_length=255, null=True)
    confirm_start_conversation = Boolean(default=False)
