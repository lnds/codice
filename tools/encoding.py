import chardet


def detect_encoding(filename):
    with open(filename, 'rb') as f:
        result = chardet.detect(f.read())
        return result['encoding']
