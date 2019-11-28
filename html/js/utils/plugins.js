/**
 * Add formatted default, maximum and minimum values to given ports in/output
 * @param  {object} ioPort in/output port
 * @return {array} formatted values of in/output port
 */
function format(ioPort) {
  var formattedIoPort = {
    "default": formatValue(ioPort.ranges.default),
    "maximum": formatValue(ioPort.ranges.maximum),
    "minimum": formatValue(ioPort.ranges.minimum),
  }
  return formattedIoPort;
}

/**
 * Compute formatted value
 * @param  {number} value
 * @return {string} formatted value
 */
function formatValue(value) {
  var formattedValue = formatNum(Math.floor(value * 100) / 100);
  return formattedValue;
}

/**
 * Compute formatted num
 * @param  {number} x
 * @return {string} formatted string
 */
function formatNum(x) {
    var parts = x.toString().split(".");
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return parts.join(".");
}
