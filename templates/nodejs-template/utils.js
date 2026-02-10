/**
 * Funções Utilitárias
 * Funções auxiliares reutilizáveis para automação
 */

/**
 * Logger simples com níveis de log
 */
const logger = {
  levels: {
    debug: 0,
    info: 1,
    warn: 2,
    error: 3,
  },

  currentLevel: process.env.LOG_LEVEL || 'info',

  log(level, ...args) {
    const levelValue = this.levels[level] || this.levels.info;
    const currentLevelValue = this.levels[this.currentLevel] || this.levels.info;

    if (levelValue >= currentLevelValue) {
      const timestamp = new Date().toISOString();
      console.log(`[${timestamp}] [${level.toUpperCase()}]`, ...args);
    }
  },

  debug(...args) {
    this.log('debug', ...args);
  },

  info(...args) {
    this.log('info', ...args);
  },

  warn(...args) {
    this.log('warn', ...args);
  },

  error(...args) {
    this.log('error', ...args);
  },
};

/**
 * Retorna timestamp atual formatado
 * @returns {string} Timestamp no formato YYYY-MM-DD_HH-MM-SS
 */
function getTimestamp() {
  const now = new Date();
  return now
    .toISOString()
    .replace(/T/, '_')
    .replace(/:/g, '-')
    .slice(0, 19);
}

/**
 * Valida se as variáveis de ambiente necessárias estão definidas
 * @param {string[]} requiredVars - Lista de nomes de variáveis obrigatórias
 * @throws {Error} Se alguma variável obrigatória não estiver definida
 */
function validateEnvVars(requiredVars) {
  const missingVars = requiredVars.filter((varName) => !process.env[varName]);

  if (missingVars.length > 0) {
    throw new Error(
      `Variáveis de ambiente faltando: ${missingVars.join(', ')}`
    );
  }
}

/**
 * Sleep/delay assíncrono
 * @param {number} ms - Tempo em milissegundos
 * @returns {Promise<void>}
 */
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

module.exports = {
  logger,
  getTimestamp,
  validateEnvVars,
  sleep,
};
