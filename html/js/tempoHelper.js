// List of all subdividers' values and labels
var dividers = [{
    value: 0.333,
    label: "2T"
  },
  {
    value: 0.5,
    label: "2"
  },
  {
    value: 0.75,
    label: "2."
  },{
    value: 0.666,
    label: "1T"
  },
  {
    value: 1,
    label: "1"
  },
  {
    value: 1.5,
    label: "1."
  },
  {
    value: 1.333,
    label: "1/2T"
  },
  {
    value: 2,
    label: "1/2"
  },
  {
    value: 3,
    label: "1/2."
  },
  {
    value: 2.666,
    label: "1/4T"
  },
  {
    value: 4,
    label: "1/4"
  },
  {
    value: 6,
    label: "1/4."
  },
  {
    value: 5.333,
    label: "1/8T"
  },
  {
    value: 8,
    label: "1/8"
  },
  {
    value: 12,
    label: "1/8."
  },
  {
    value: 10.666,
    label: "1/16T"
  },
  {
    value: 16,
    label: "1/16"
  },
  {
    value: 24,
    label: "1/16."
  },
  {
    value: 21.333,
    label: "1/32T"
  },
  {
    value: 32,
    label: "1/32"
  },
  {
    value: 48,
    label: "1/32."
  }
];

var unitConversionFactors = {
  // to/from s:
  s: {
    to: 1,
    from: 1
  },
  ms: {
    to: 0.001,
    from: 1000
  },
  min: {
    to: 60.0,
    from: 1 / 60.0,
  },
  // to/from Hz:
  Hz: {
    to: 1,
    from: 1,
  },
  MHz: {
    to: 1000000,
    from: 0.000001,
  },
  kHz: {
    to: 1000,
    from: 0.001,
  }
};


/**
 * Get list of filtered dividers s such as sMin <= s <= sMax
 * @param  {float} sMin min divider value
 * @param  {float} sMax max divider value
 * @return {array}      array of filtered dividers as objects with subdivider value and label
 */
function getFilteredDividers(sMin, sMax) {
  var filteredDividers = [];
  for (i = 0; i < dividers.length; i++) {
    if (sMin <= dividers[i].value && dividers[i].value <= sMax) {
      filteredDividers.push(dividers[i]);
    }
  }
  return filteredDividers;
}

/**
 *
 * Compute divider value
 * @param  {float} b BPM s-1
 * @param  {float} v ControlPort value in seconds
 * @return  {float} Divider value
 */
function getDividerValue(b, v) {
  return 240 / (b * v);
}

/**
 *
 * Compute Control Port value if BPM addressed
 * @param  {float} b BPM s-1
 * @param  {float} s divider value (subdivider)
 * @return  {float} Control Port value in seconds
 */
function getPortValue(b, s) {
  return 240 / (b * s);
}

/**
 *
 * Convert value in any of the listed units to equivalent in seconds
 * or value in seconds to any of the listed units
 * @param  {float} value            Input value
 * @param  {float} conversionFactor  Conversion factor based on unitConversionFactors
 * @param  {string} portUnitSymbol       Control port unit symbol
 * @return {float}                  Output value
 */
function convertEquivalent(value, conversionFactor, portUnitSymbol) {
  // var portUnitSymbol = port.units.symbol;
  if (portUnitSymbol === "s" || portUnitSymbol === "ms" || portUnitSymbol === "min") {
    var v = conversionFactor * value;
    return  parseFloat(v.toFixed(3));
  } else if (portUnitSymbol === "Hz" || portUnitSymbol === "MHz" || portUnitSymbol === "kHz") {
    if (value === 0) { // avoid division by zero
      value = 0.001;
    }
    var v = conversionFactor / value;
    return parseFloat(v.toFixed(3));
  } else {
    return;
  }
}

/**
 *
 * Convert value in seconds to control port unit
 * @param       {float} value Value in seconds
 * @param       {string} portUnitSymbol       Control port unit symbol
 * @return      {float} Equivalent value using control port unit
 */
function convertSecondsToPortValueEquivalent(value, portUnitSymbol) {
  var unit = unitConversionFactors[portUnitSymbol]
  if (unit === undefined) {
    // TODO handle error
    return;
  }
  var conversionFactor = unit.from;
  return convertEquivalent(value, conversionFactor, portUnitSymbol);
}

/**
 *
 * Convert value from one of the listed units to seconds equivalent
 * @param       {float} value Control port value (usually min or max)
 * @param       {string} portUnitSymbol       Control port unit symbol
 * @return      {float} Equivalent value in seconds
 */
function convertPortValueToSecondsEquivalent(value, portUnitSymbol) {
  var unit = unitConversionFactors[portUnitSymbol]
  if (unit === undefined) {
    // TODO handle error
    return;
  }
  var conversionFactor = unit.to;
  return convertEquivalent(value, conversionFactor, portUnitSymbol);
}

/**
 * Get list of possible port values based on bpm and list of dividers
 * @param  {string} portUnitSymbol       Control port unit symbol
 * @param  {float} b        bpm
 * @param  {array} dividerOptions array of objects { value: dividerValue, label: dividerLabel }
 * @return {array}          array of objects { value: portValue, label: dividerLabel }
 */
function getOptionsPortValues(portUnitSymbol, b, dividerOptions) {
  if (!dividerOptions) {
    return;
  }
  var portValuesWithDividerLabels = [];
  for (i = 0; i < dividerOptions.length; i++) {
    var portValueSec = getPortValue(b, dividerOptions[i].value);
    var portValue = convertSecondsToPortValueEquivalent(portValueSec, portUnitSymbol);
    portValuesWithDividerLabels.push({ value: portValue, label: dividerOptions[i].label });
  }
  return portValuesWithDividerLabels;
}

/**
 * Get dividers options for given port and bpmPort min and max
 * @param  {object} port Port info
 * @param  {float} minBpm    minimum value for bpm
 * @param  {float} maxBpm    maximum value for bpm
 * @return {array}      array of all available dividers as objects with subdivider value and label
 */
function getDividerOptions(port, minBpm, maxBpm) {
  // First, convert min and max port values to equivalent in seconds
  var min = convertPortValueToSecondsEquivalent(port.ranges.minimum, port.units.symbol);
  var max = convertPortValueToSecondsEquivalent(port.ranges.maximum, port.units.symbol);

  // OLD
  // var s1 = getDividerValue(bpmPort.value, min)
  // var s2 = getDividerValue(bpmPort.value, max)
  // var sMin = s1 < s2 ? s1 : s2
  // var sMax = s1 < s2 ? s2 : s1

  // Then, compute min and max subdividers that will fit all bpms
  var s1minBpm = getDividerValue(minBpm, min);
  var s2minBpm = getDividerValue(minBpm, max);
  var s1maxBpm = getDividerValue(maxBpm, min);
  var s2maxBpm = getDividerValue(maxBpm, max);

  if (hasStrictBounds(port)) {
    var sMin = s1minBpm < s2minBpm ? Math.max(s1minBpm, s1maxBpm) : Math.max(s2minBpm, s2maxBpm);
    var sMax = s1minBpm < s2minBpm ? Math.min(s2minBpm, s2maxBpm) : Math.min(s1minBpm, s1maxBpm);
  } else { // all possible dividers
    var sMin = Math.min(s1minBpm, s2minBpm, s1maxBpm, s2maxBpm);
    var sMax = Math.max(s1minBpm, s2minBpm, s1maxBpm, s2maxBpm);
  }


  // Finally, filter options s such as sMin <= s <= sMax
  return getFilteredDividers(sMin, sMax);
}

/**
 * Check if port has lv2:portProperty  mod:tempoRelatedDynamicScalePoints;
 * @param  {string}  port port infos
 * @return {Boolean}
 */
function hasTempoRelatedDynamicScalePoints(port) {
  return port.properties.indexOf("tempoRelatedDynamicScalePoints") > -1
  // return designation === "http://lv2plug.in/ns/ext/time/#beatsPerMinute" || designation === "http://lv2plug.in/ns/ext/time#beatsPerMinute"
}

/**
 * Check if port has lv2:portProperty  mod:hasStrictBounds;
 * @param  {string}  port port infos
 * @return {Boolean}
 */
function hasStrictBounds(port) {
  return port.properties.indexOf("hasStrictBounds") > -1
}
