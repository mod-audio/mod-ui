// List of all subdividers' values and labels
var dividers = [{
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
 * @return {array}      array of filtered dividers as objects with value and label
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
  return 240 / (b*v);
}

/**
 *
 * Compute Control Port value if BPM addressed
 * @param  {float} b BPM s-1
 * @param  {float} s divider
 * @return  {float} Control Port value in seconds
 */
function getPortValue(b, s) {
  return 240 / (b*s);
}

/**
 *
 * Convert value in any of the listed units to equivalent in seconds
 * or value in seconds to any of the listed units
 * @param  {float} value            Input value
 * @param  {float} conversionFactor  Conversion factor based on unitConversionFactors
 * @param  {object} port             Control port object
 * @return {float}                  Output value
 */
function convertEquivalent(value, conversionFactor, port) {
  var unitSymbol = port.units.symbol;
  if (unitSymbol === "s" || unitSymbol === "ms" || unitSymbol === "min") {
    return conversionFactor * value;
  } else if (unitSymbol === "Hz" || unitSymbol === "MHz" || unitSymbol === "kHz") {
    if (value === 0) { // avoid division by zero
      value = 0.001;
    }
    return conversionFactor / value;
  } else {
    // TODO how to handle other units? error?
  }
}

/**
 *
 * Convert value in seconds to control port unit
 * @param       {float} value Value in seconds
 * @param       {object} port  Port object with unit info
 * @return      {float} Equivalent value using control port unit
 */
function convertSecondsToPortValueEquivalent(value, port) {
  var unit = unitConversionFactors[port.units.symbol]
  if (unit === undefined) {
    // TODO handle error
    return;
  }
  var conversionFactor = unit.from;
  return convertEquivalent(value, conversionFactor, port);
}

/**
 *
 * Convert value from one of the listed units to seconds equivalent
 * @param       {float} value Control port value (usually min or max)
 * @param       {object} port  Port object with unit info
 * @return      {float} Equivalent value in seconds
 */
function convertPortValueToSecondsEquivalent(value, port) {
  var unit = unitConversionFactors[port.units.symbol]
  if (unit === undefined) {
    // TODO handle error
    return;
  }
  var conversionFactor = unit.to;
  return convertEquivalent(value, conversionFactor, port);
}

/**
 * Get list of possible port values based on bpm and list of dividers
 * @param  {object} port     Port object with unit info
 * @param  {float} b        bpm
 * @param  {array} dividerOptions array of objects { value: dividerValue, label: dividerLabel}
 * @return {array}          array of objects { value: portValue, label: dividerLabel}
 */
function getOptionsPortValues(port, b, dividerOptions) {
  if (!dividerOptions) {
    return;
  }
  var portValuesWithDividerLabels = [];
  for (i = 0; i < dividerOptions.length; i++) {
    var portValueSec = getPortValue(b, dividerOptions[i].value);
    var portValue = convertSecondsToPortValueEquivalent(portValueSec, port);
    portValuesWithDividerLabels.push({ value: portValue, label: dividerOptions[i].label });
  }
  return portValuesWithDividerLabels;
}
