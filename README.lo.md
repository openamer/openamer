# OpenAmer Agent

**ຕົວແທນ AI ທີ່ພັດທະນາຕົນເອງໄດ້ — ຮຽນຮູ້ຈາກປະສົບການ, ສ້າງທັກສະ, ຈື່ຈຳຄວາມມັກຂອງທ່ານ, ແລະ ເຮັດວຽກໃຫ້ທ່ານໄດ້ທຸກບ່ອນ.**

ໃຊ້ໂມເດລໃດກໍໄດ້ທີ່ທ່ານຕ້ອງການ — OpenRouter, OpenAI, DeepSeek ແລະ ອື່ນໆ. ປ່ຽນໄດ້ດ້ວຍ `openamer model` — ໂດຍບໍ່ຕ້ອງປ່ຽນໂຄ້ດ.

## ຄຸນສົມບັດ

- **ອິນເຕີເຟສ Terminal ແທ້ — TUI ແບບເຕັມຮູບແບບ ພ້ອມລະບົບ autocomplete, ປະຫວັດການນຳໃຊ້ (history), ແລະ ການສະແດງຜົນຂອງເຄື່ອງມືແບບ streaming**
- **ຢູ່ບ່ອນທີ່ທ່ານໃຊ້ — Telegram, Discord, Slack, WhatsApp ແລະ ອື່ນໆ ຜ່ານ gateway ດຽວ**
- **ຮຽນຮູ້ໄດ້ຕາມການເວລາ — ຄວາມຈຳ, ທັກສະທີ່ພັດທະນາຕົນເອງໄດ້, ການຈື່ຈຳຂໍ້ມູນຂ້າມເຊດຊັນ (cross-session recall)**
- **ມອບໝາຍ & ປະມວນຜົນຂະໜານ — ສ້າງ subagents ເພື່ອເຮັດວຽກແບບຂະໜານ**
- **ການເຮັດວຽກອັດຕະໂນມັດຕາມກຳນົດເວລາ — ລະບົບ cron ທີ່ຕິດຕັ້ງມາໃນຕົວ ສຳລັບລາຍງານປະຈຳວັນ, ການສຳຮອງຂໍ້ມູນ ແລະ ການກວດສອບ**
- **ເຮັດວຽກໄດ້ທຸກບ່ອນ — ທັງໃນເຄື່ອງ (local), Docker, SSH, cloud, serverless**

## ຕິດຕັ້ງແບບດ່ວນ

Windows (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## ເລີ່ມຕົ້ນນຳໃຊ້

```bash
openamer              # ເລີ່ມຕົ້ນການສົນທະນາ
openamer setup        # ຕັ້ງຄ່າ API keys ແລະ ຜູ້ໃຫ້ບໍລິການ (provider) ຂອງທ່ານ
openamer model        # ເລືອກໂມເດລຂອງທ່ານ
openamer update       # ອັບເດດເປັນເວີຊັນຫຼ້າສຸດ
```

## ກຳລັງອັບເດດ

OpenAmer ຈະກວດສອບການອັບເດດໂດຍອັດຕະໂນມັດ ແລະ ສະແດງຄຳເຕືອນໃນແຖບ banner ຕ້ອນຮັບ. ໃຫ້ໃຊ້ຄຳສັ່ງ `openamer update` ເພື່ອຕິດຕັ້ງເວີຊັນຫຼ້າສຸດ — ເຊິ່ງມັນຈະສຳຮອງຂໍ້ມູນຂອງທ່ານກ່ອນ.

## ການມີສ່ວນຮ່ວມ

ຍິນດີຕ້ອນຮັບການມີສ່ວນຮ່ວມ — ເປີດ issues, ສົ່ງ pull requests, ຫຼື ເຂົ້າຮ່ວມຊຸມຊົນ.

## ໃບອະນຸຍາດ

ສັນຍາອະນຸຍາດ Apache 2.0. ເບິ່ງ {LICENSE}.
