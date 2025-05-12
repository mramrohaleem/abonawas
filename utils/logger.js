const { createLogger, format, transports } = require('winston');
const { v4: uuidv4 } = require('uuid');

const logger = createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: format.combine(
    format.timestamp(),
    format.printf(({ timestamp, level, message, ...meta }) => {
      const traceId = meta.trace || '';
      const rest = Object.entries(meta).filter(([k])=>k!=='trace').map(([k,v])=>`${k}=${JSON.stringify(v)}`).join(' ');
      return `${timestamp} [${traceId}] ${level}: ${message} ${rest}`;
    })
  ),
  transports: [new transports.Console()],
});

function trace() { return uuidv4().split('-')[0]; }

['info','warn','error','debug'].forEach(lvl => {
  const orig = logger[lvl];
  logger[lvl] = (msg, meta={}) => orig.call(logger, msg, meta);
});
logger.trace = trace;

module.exports = logger;
