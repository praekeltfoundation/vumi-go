from twisted.internet.defer import inlineCallbacks, returnValue


class ModelObjectCache(object):
    """
    Low-TTL cache for model data to avoid hitting Riak too much.
    """
    def __init__(self, reactor, ttl):
        self._reactor = reactor
        self._ttl = ttl
        self._models = {}
        self._evictors = {}

    def evict_model_entry(self, key):
        """
        Remove an model from the cache.
        """
        del self._models[key]
        del self._evictors[key]

    def schedule_eviction(self, key):
        """
        Schedule the eviction of a cached model.
        """
        if key in self._evictors:
            # We already have an evictor for this model, so we don't
            # need a new one.
            return
        delayed_call = self._reactor.callLater(
            self._ttl, self.evict_model_entry, key)
        self._evictors[key] = delayed_call

    def cleanup(self):
        """
        Clean up all remaining state.
        """
        # We use .items() instead of .iteritems() here because we modify
        # self._evictors in the loop.
        for key, delayed_call in self._evictors.items():
            delayed_call.cancel()
            self.evict_model_entry(key)

    @inlineCallbacks
    def get_model(self, model_getter, key):
        """
        Return the model using the provided getter function and key.

        If the model is not cached, it will be fetched from Riak. If
        caching is not disabled, it will also be added to the cache and
        eviction scheduled.
        """
        if key not in self._models:
            # Fetching the model returns control to the reactor and
            # gives other things the opportunity to cache the model
            # behind our back. If this happens, we replace the cached model
            # (the one we fetched may be newer) and let schedule_eviction()
            # worry about the existing evictor.
            model = yield model_getter(key)
            if self._ttl <= 0:
                # Special case for disabled cache.
                returnValue(model)
            self._models[key] = model
            self.schedule_eviction(key)
        returnValue(self._models[key])
