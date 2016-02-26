/*!
 * lunr.tokenizer
 * Copyright (C) @YEAR Oliver Nightingale
 */

/**
 * A function for splitting a string into tokens ready to be inserted into
 * the search index.
 *
 * @module
 * @param {String} obj The string to convert into tokens
 * @returns {Array}
 */
lunr.tokenizer = function (obj) {
  if (!arguments.length || obj == null || obj == undefined) return []
  if (Array.isArray(obj)) return obj.map(function (t) { return t.toLowerCase() })

  var words = obj.toString().trim().toLowerCase().split(/[\s\-]+/)

  function break_words(word, num) {
      var slices = []
      var length = word.length-num+1
      for (var i=1; i<length; i++) {
          slices[word.substring(i, word.length)] = true
      }
      return Object.keys(slices)
  }

  var nwords = []
  for (var i in words) {
      Array.prototype.push.apply(nwords, break_words(words[i], 3))
  }

  return nwords.concat(words)
}
