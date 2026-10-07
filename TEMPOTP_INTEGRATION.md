# TempOTP integration

TempOTP has been added as a third gateway provider.

- Provider: `tempotp`
- Default Service ID: `1846`
- Country: `22` (India)
- API base: `https://api.tempotp.online`
- Buy: `buyNumber`
- SMS: `checkSms`
- Cancel: `cancelNumber`
- Balance: `getBalance`
- Services: `getServices`
- Servers: `getServers`

The dashboard now has one shared Service ID input. Provider changes set the default:

- 4SIM -> `1929`
- OTPDoctor -> `16311`
- TempOTP -> `1846`

TempOTP cancellation follows the existing cancellation policy with up to 8 cancel attempts. When an OTP has already been received, TempOTP is not cancelled because the documented API does not provide a finish endpoint.

The TempOTP API key is configured in `config.py`. For security, rotate the key if it has been shared publicly and replace it in the configuration.
