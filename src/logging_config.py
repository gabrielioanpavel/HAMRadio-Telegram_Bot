import logging

class NoInfoFilter(logging.Filter):
    def filter(self, record) -> bool:
        return record.levelno != logging.INFO
    
class OnlyInfoFilter(logging.Filter):
    def filter(self, record) -> bool:
        return record.levelno == logging.INFO

def setup_logger() -> logging.Logger:
    logger = logging.getLogger('BotLogger')
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(levelname)s] at %(asctime)s - %(message)s')

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.addFilter(OnlyInfoFilter())
    ch.setFormatter(formatter)

    # File handler
    fh = logging.FileHandler('log.txt')
    fh.setLevel(logging.DEBUG)
    fh.addFilter(NoInfoFilter())
    fh.setFormatter(formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)
    
    return logger
