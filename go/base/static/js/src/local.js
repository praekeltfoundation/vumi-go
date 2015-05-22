(function(exports) {
  function set(k, v) {
    localStorage.setItem(k, JSON.stringify(v));
  }


  function get(k, defaultVal) {
    return k in localStorage || arguments.length < 2
      ? JSON.parse(localStorage.getItem(k))
      : defaultVal;
  }


  exports.set = set;
  exports.get = get;
})(go.local = {});
