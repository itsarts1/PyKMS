import os.path
try:
    import random
except ImportError:
    import upy.fakerandom as random
import time
try:
    import uuid
except ImportError:
    import upy.uuid as uuid

from xmltok import tokenize
from uxml2dict import parse
kmsdb = os.path.join(os.path.dirname(__file__), 'KmsDataBase.xml')

platform_id = 3612

fallback_group_id = 206
fallback_key_id_min = 551000000
fallback_key_id_max = 570999999

# release for windows 10 1809
minTime = time.mktime((2018, 10, 2, 0, 0, 0, 0, 0, 0))

os_build = '17763.0000'

def epidGenerator(kmsId, version, lcid):
    # Generate Part 2: Group ID and Product Key ID Range
    xml = parse(tokenize(open(kmsdb)), lesslist=False)
    for item in xml['KmsData'][0]['CsvlkItems'][0]['CsvlkItem']:
        if '@VlmcsdIndex' in item and kmsId in [uuid.UUID(kms_item['@KmsItem']) for kms_item in item['Activate']]:
            group_id, key_id_min, key_id_max = int(item['@GroupId']), int(item['@MinKeyId']), int(item['@MaxKeyId'])
            break
    else:
        for item in xml['KmsData'][0]['CsvlkItems'][0]['CsvlkItem']:
            if kmsId in [uuid.UUID(kms_item['@KmsItem']) for kms_item in item['Activate']]:
                group_id, key_id_min, key_id_max = int(item['@GroupId']), int(item['@MinKeyId']), int(item['@MaxKeyId'])
                break
        else:
            group_id, key_id_min, key_id_max = fallback_group_id, fallback_key_id_min, fallback_key_id_max


    # Generate Part 3 and Part 4: Product Key ID
    productKeyID = random.randint(key_id_min, key_id_max)

    # Generate Part 5: License Channel (00=Retail, 01=Retail, 02=OEM,
    # 03=Volume(GVLK,MAK)) - always 03
    licenseChannel = 3

    # Generate Part 6: Language - use system default language
    # 1033 is en-us
    languageCode = lcid # C# CultureInfo.InstalledUICulture.LCID

    # Generate Part 8: KMS Host Activation Date
    # Generate Year and Day Number
    randomDate = random.randint(int(minTime), int(time.time()))
    randomYear = time.localtime(randomDate)[0]
    firstOfYear = time.mktime((randomYear, 1, 1, 0, 0, 0, 0, 0, 0))
    randomDayNumber = int((randomDate - firstOfYear) / 86400 + 0.5)

    # generate the epid string
    return '%05d-%05d-%03d-%06d-%02d-%04d-%s-%03d%04d' % (
        platform_id, group_id, productKeyID // 1000000, productKeyID % 1000000,
        licenseChannel, languageCode, os_build, randomDayNumber, randomYear
    )
