LOG_LEVEL_DEBUG_TERMINAL = 0
LOG_LEVEL_DEBUG_FILE = 1
LOG_LEVEL_RELEASE = 2

SAVE_LOG_FILE_CHART = False

SLIPPAGE_BUY = 0.5
SLIPPAGE_SELL = 0.5

def logging(logger, logLevel, log):
    if logLevel == LOG_LEVEL_DEBUG_TERMINAL:
        print(log)
    if logLevel == LOG_LEVEL_DEBUG_FILE:
        logger.info(log)