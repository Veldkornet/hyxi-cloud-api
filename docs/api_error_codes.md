# HYXI API Error Codes

## Authentication Exception

| Error code | Error Info |
|---|---|
| `A000001` | Authentication failed |
| `A000002` | Invalid access token |
| `A000003` | User information does not exist |
| `A000004` | Invalid credentials |
| `A000005` | Signature verification failed |
| `A000006` | Request time differs significantly from server time |
| `A000007` | The length of signature header fields cannot exceed five |
| `A000008` | Refresh token is not supported |
| `A000009` | Invalid refresh_token |
| `A000010` | Token has expired, please obtain a new one |
| `A000011` | Unknown scope, please login again |
| `A000012` | No access permission for this resource |

## Common Exception

| Error code | Error Info |
|---|---|
| `0` | Success |
| `C000001` | Parameter error |
| `C000002` | Request frequency exceeded |
| `C000003` | No HTTP information obtained |
| `C000004` | Request failed, please try again later |
| `C000005` | Unsupported request method |
| `C000006` | User information not found, please re-login or check the token |
| `C000007` | Invalid response data |
| `C000008` | RSA encryption failed |
| `C000009` | RSA decryption failed |
| `C000010` | AES encryption failed |
| `C000011` | AES decryption failed |
| `C999999` | Service exception, please contact the service provide |

## Business Exception

| Error code | Error Info |
|---|---|
| `B001001` | Device does not exist |
| `B001002` | SN number format is incorrect |
| `B001003` | Failed to obtain the device’s initial registration information |
| `B001004` | There are devices without operation permissions, please check and retry |
| `B001005` | Device bind failed |
| `B001006` | Failed to issue device networking command, please try again later |
| `B001007` | SN translation mapping failed, please try again later |
| `B001008` | Unknown device type, please check SN and try again |
| `B002001` | Failed to issue instruction |
| `B002002` | Device count exceeds the limit |
| `B002003` | No permission to operate this device |
| `B002004` | Instruction parameter error |
| `B002005` | The number of instructions per request cannot exceed 10 |
| `B003001` | Both phone number and email cannot be empty |
| `B003002` | Registration has timed out, please try again |
| `B003003` | Username/phone number/email already exists |
| `B003004` | Account or password is incorrect |
| `B003005` | Login failed, please contact the service provider |
| `B003006` | AccessKey already exists, please switch |
| `B003007` | There are applications without operation permissions, please check and retry |
| `B003008` | Account registration failed, please contact the service provider |
| `B003009` | Verification code sending failed |
| `B003010` | Phone number registered |
| `B003011` | Email registered |
| `B003012` | The verification code is obtained too frequently |
| `B003013` | Verification code error |
| `B003014` | No corresponding account information found |
| `B003015` | The password does not meet specifications |
| `B003016` | Account already exists |
| `B004001` | Data push task execution failed |
| `B004002` | At least one device sn has been subscribed to repeatedly |
| `B005001` | Data does not exist |
| `B006001` | Failed to create a plant |
| `B006002` | Failed to modify the plant |
| `B006003` | Failed to delete plant |
| `B006004` | Failed to set plant tariff |
| `B006005` | Plant parameter error |
| `B006006` | Plant does not exist |
| `B006007` | No permission to operate this plant |
| `B006008` | Long name of the plant |
| `B006009` | Incorrect type of plant |
| `B006010` | Plant currency unit error |
| `B006011` | Incorrect type of tariff for the plant |
| `B006012` | Incorrect formatting of the time zone of the plant |
| `B007001` | Alarm handling failure |
| `B008001` | An online document with the same name already exists |
| `B008002` | the project info is not exist |
| `B008003` | the documents save failed |
| `B008004` | the document info is not exist |
| `B008005` | No operation permission |
| `B009001` | File format error |
