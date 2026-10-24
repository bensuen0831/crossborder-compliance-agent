# Security findings disposition

產品 `733a7483439cd919c186ed0064b8f3752904ebb6`；前一產品 `4593a355d0711a9ba955b1624926a2ec71d60430`；前一獨立證據 `d9adf53241c8e86ec264913713bf52b2fedcc36e`。本輪工程核實／建議不是正式 Reviewer 決定。

原始每映像134High/1Critical=135套件findings、44唯一CVE；基線包含7CI映像+1實際RC1本機映像，共8個不同config identity、1080個package×image occurrences。不能稱135個不同漏洞。

使用同一最新DB重掃舊映像：135High/1Critical；新映像：130High/1Critical、45唯一CVE。修復移除6個非必要套件，其中5筆High occurrences（同CVE-2026-24882）消失；其餘必需gpg/gpgconf/gpgv仍受同CVE影響，故唯一CVE沒有因此減少。新增libbrotli1/CVE-2026-111497來自新DB，舊映像同樣存在；不是本次新增依賴造成。未使用ignore-unfixed、suppression、降門檻或自動風險接受。

每筆原始finding完整欄位、PkgID、原報告索引／hash、全部映像映射、官方source/version/release status、修復建議、暴露及Reviewer欄位見security_findings_disposition.json。原始scanner未提供FindingID時保留null，KB01-SEC-*只是可追溯工程occurrence ID。

| ID | CVE | Package/version | Original | New local | Recommendation | Reviewer |
|---|---|---|---|---|---|---|
| KB01-SEC-e81b00c6a79fd420 | CVE-2026-76642 | bsdutils 1:2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-35e8f76f1bd80dca | CVE-2026-78408 | bsdutils 1:2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-092ca95927dc993f | CVE-2026-78409 | bsdutils 1:2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-0a8c39c85af36c92 | CVE-2026-78410 | bsdutils 1:2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-9a3e29c1dac1ac35 | CVE-2026-20213 | clamav 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-8b7c5a50b29a5600 | CVE-2026-20214 | clamav 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-51b59cdc4422b722 | CVE-2026-20215 | clamav 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-c640fa9887d6ef83 | CVE-2026-20216 | clamav 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-c75bc219378793b5 | CVE-2026-20217 | clamav 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-7d4536f4331bbcb2 | CVE-2026-20243 | clamav 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-0933ec123f6f4679 | CVE-2026-20244 | clamav 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-f36d754d4967b2d7 | CVE-2026-20213 | clamav-base 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-d6eec2de42072226 | CVE-2026-20214 | clamav-base 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-1474ef2944c14562 | CVE-2026-20215 | clamav-base 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-06ac9a1b68022c62 | CVE-2026-20216 | clamav-base 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-0abdb9e29730f69c | CVE-2026-20217 | clamav-base 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-f8b7fc6446ed3e38 | CVE-2026-20243 | clamav-base 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-38f678d660a3c4bd | CVE-2026-20244 | clamav-base 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-bb084e6bc699cdd7 | CVE-2026-20213 | clamav-freshclam 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-cc996c12c52dd9b0 | CVE-2026-20214 | clamav-freshclam 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-a96fd928de92f4b6 | CVE-2026-20215 | clamav-freshclam 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-a709fbe5a7aad19a | CVE-2026-20216 | clamav-freshclam 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-dd099af3b6d240d4 | CVE-2026-20217 | clamav-freshclam 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-140acc0fe82df74a | CVE-2026-20243 | clamav-freshclam 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-108a2b2b8f6a7906 | CVE-2026-20244 | clamav-freshclam 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-4f76bfc44ffa690e | CVE-2026-24882 | dirmngr 2.4.7-21+deb13u1+b5 | HIGH | REMOVED_FROM_NEW_IMAGE | Verify removed occurrence | PENDING |
| KB01-SEC-a2988898705f4794 | CVE-2026-24882 | gnupg 2.4.7-21+deb13u1 | HIGH | REMOVED_FROM_NEW_IMAGE | Verify removed occurrence | PENDING |
| KB01-SEC-9904c8e535cb84f7 | CVE-2026-24882 | gnupg-l10n 2.4.7-21+deb13u1 | HIGH | REMOVED_FROM_NEW_IMAGE | Verify removed occurrence | PENDING |
| KB01-SEC-8685691d25816619 | CVE-2026-24882 | gpg 2.4.7-21+deb13u1+b5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-45b3e547ede4264a | CVE-2026-24882 | gpg-agent 2.4.7-21+deb13u1+b5 | HIGH | REMOVED_FROM_NEW_IMAGE | Verify removed occurrence | PENDING |
| KB01-SEC-e4e6d1b4c239f89e | CVE-2026-24882 | gpgconf 2.4.7-21+deb13u1+b5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-eaf6a5415bbff5a0 | CVE-2026-24882 | gpgsm 2.4.7-21+deb13u1+b5 | HIGH | REMOVED_FROM_NEW_IMAGE | Verify removed occurrence | PENDING |
| KB01-SEC-6db5fd42e23545f5 | CVE-2026-24882 | gpgv 2.4.7-21+deb13u1+b5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-1343b47e129a01da | CVE-2026-54369 | libacl1 2.3.2-2+b1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-f2b7be29c17c6122 | CVE-2026-76642 | libblkid1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-db34d1bbb59b3636 | CVE-2026-78408 | libblkid1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-a70368775930f937 | CVE-2026-78409 | libblkid1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-8a8f209e1ad64834 | CVE-2026-78410 | libblkid1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-a63c278e9f8083a4 | CVE-2026-20213 | libclamav12 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-d361454d483fd800 | CVE-2026-20214 | libclamav12 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-095ca1e5b07c3794 | CVE-2026-20215 | libclamav12 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-0cb906f9b5a34457 | CVE-2026-20216 | libclamav12 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-0aeec37b3132ae38 | CVE-2026-20217 | libclamav12 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-af369505c368e666 | CVE-2026-20243 | libclamav12 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-abf9311c6b92393d | CVE-2026-20244 | libclamav12 1.4.3+dfsg-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-4af0846a756ad2af | CVE-2026-34980 | libcups2t64 2.4.10-3+deb13u2 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-37350df372866179 | CVE-2026-55453 | libcups2t64 2.4.10-3+deb13u2 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-7148d3a45107db15 | CVE-2026-12064 | libcurl3t64-gnutls 8.14.1-2+deb13u7 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-cfaac63b3f5bb422 | CVE-2026-8458 | libcurl3t64-gnutls 8.14.1-2+deb13u7 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-7b3fe481fc4e4dd7 | CVE-2026-12064 | libcurl4t64 8.14.1-2+deb13u7 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-62b410e4fb45531c | CVE-2026-8458 | libcurl4t64 8.14.1-2+deb13u7 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-d538e56ff7d6b4f6 | CVE-2026-86476 | libgstreamer-plugins-base1.0-0 1.26.2-1+deb13u2 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-ba9ec00f8ab95a9a | CVE-2026-76642 | liblastlog2-2 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-542f065ea92c377d | CVE-2026-78408 | liblastlog2-2 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-f33e1e3e13308b1d | CVE-2026-78409 | liblastlog2-2 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-dcfa15d9a2761d36 | CVE-2026-78410 | liblastlog2-2 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-a4de2b177ec82826 | CVE-2026-76642 | libmount1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-ffd95d89d40215a8 | CVE-2026-78408 | libmount1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-ccdd678721d09b76 | CVE-2026-78409 | libmount1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-b42c2e885e14635f | CVE-2026-78410 | libmount1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-e766c0e85726cdbf | CVE-2025-69720 | libncursesw6 6.5+20250216-2 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-b393ae3d1063f2a9 | CVE-2026-15308 | libpython3.13-minimal 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-ffc6560b5a956260 | CVE-2026-19445 | libpython3.13-minimal 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-c15785f71a7b5da5 | CVE-2026-19553 | libpython3.13-minimal 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-69529fd8ac3c52ad | CVE-2026-7210 | libpython3.13-minimal 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-76db6842b457d764 | CVE-2026-82049 | libpython3.13-minimal 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-ee4176838c43c566 | CVE-2026-15308 | libpython3.13-stdlib 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-c065b656d41ddb1d | CVE-2026-19445 | libpython3.13-stdlib 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-a8dcb1d8fdd08a95 | CVE-2026-19553 | libpython3.13-stdlib 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-9fa27a9b400c511e | CVE-2026-7210 | libpython3.13-stdlib 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-c1cf25ca46c0b158 | CVE-2026-82049 | libpython3.13-stdlib 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-187dd0108aec63f6 | CVE-2026-76642 | libsmartcols1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-cba9d7fdce23062b | CVE-2026-78408 | libsmartcols1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-704437071178046c | CVE-2026-78409 | libsmartcols1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-65c44ec86452643f | CVE-2026-78410 | libsmartcols1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-4a5a5a1ee80631cd | CVE-2026-16742 | libsystemd-shared 257.13-1~deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-ea57e975eb2b4c34 | CVE-2026-16742 | libsystemd0 257.13-1~deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-efab5f33cb063c0f | CVE-2026-73066 | libtesseract5 5.5.0-1+b1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-5a5ae39bb90ab01e | CVE-2026-88047 | libtesseract5 5.5.0-1+b1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-e22f8a6c5223aac7 | CVE-2026-88048 | libtesseract5 5.5.0-1+b1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-ce441808b5b0dd6a | CVE-2026-88051 | libtesseract5 5.5.0-1+b1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-0151c7d99acae728 | CVE-2026-88052 | libtesseract5 5.5.0-1+b1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-4e0c565a110c07f2 | CVE-2026-88053 | libtesseract5 5.5.0-1+b1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-e11a34e3c45d1ab4 | CVE-2026-36849 | libtiff6 4.7.0-3+deb13u3 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-240d2c10edd8c9f2 | CVE-2026-52490 | libtiff6 4.7.0-3+deb13u3 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-cf3d00045163814f | CVE-2025-69720 | libtinfo6 6.5+20250216-2 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-a5ef20a398c4912c | CVE-2026-16742 | libudev1 257.13-1~deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-17e267bbb26780e7 | CVE-2026-76642 | libuuid1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-d5f2b74080dbec3a | CVE-2026-78408 | libuuid1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-f16f4ba1ebdfd48b | CVE-2026-78409 | libuuid1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-b79e63f4d0562adb | CVE-2026-78410 | libuuid1 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-7bf5d995fc9c4fde | CVE-2026-88806 | libx11-6 2:1.8.12-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-c15288e1c7a2db7a | CVE-2026-88806 | libx11-data 2:1.8.12-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-30020363efc5ea62 | CVE-2026-88806 | libx11-xcb1 2:1.8.12-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-26026d31584f712f | CVE-2026-6653 | libxml2 2.12.7+dfsg+really2.9.14-2.1+deb13u3 | CRITICAL | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-8507a5fa8f5929a0 | CVE-2026-74860 | libxml2 2.12.7+dfsg+really2.9.14-2.1+deb13u3 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-6be3cb4d0154ca96 | CVE-2026-86138 | libxml2 2.12.7+dfsg+really2.9.14-2.1+deb13u3 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-b61e56b7b4a853c7 | CVE-2026-86139 | libxml2 2.12.7+dfsg+really2.9.14-2.1+deb13u3 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-f7fa6c7252afd009 | CVE-2026-86140 | libxml2 2.12.7+dfsg+really2.9.14-2.1+deb13u3 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-cd138fa99f046879 | CVE-2026-86142 | libxml2 2.12.7+dfsg+really2.9.14-2.1+deb13u3 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-42d9c983fe8ced17 | CVE-2026-86143 | libxml2 2.12.7+dfsg+really2.9.14-2.1+deb13u3 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-19a17d4e21dad134 | CVE-2026-86144 | libxml2 2.12.7+dfsg+really2.9.14-2.1+deb13u3 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-2f53ba3ffd45d869 | CVE-2026-88807 | libxrender1 1:0.9.12-1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-1494200f1375cabf | CVE-2026-76642 | login 1:4.16.0-2+really2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-f66b938591fb2eaf | CVE-2026-78408 | login 1:4.16.0-2+really2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-14fbfd0bbfe6ec08 | CVE-2026-78409 | login 1:4.16.0-2+really2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-ee4c440a5e368301 | CVE-2026-78410 | login 1:4.16.0-2+really2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-fd5bca14bc45fefb | CVE-2026-76642 | mount 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-42c3ff5f8f84c6a2 | CVE-2026-78408 | mount 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-d059a561440fc98a | CVE-2026-78409 | mount 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-83a82296a84c7ce9 | CVE-2026-78410 | mount 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-68ba09ee170a2918 | CVE-2025-69720 | ncurses-base 6.5+20250216-2 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-06783f8654dc9052 | CVE-2025-69720 | ncurses-bin 6.5+20250216-2 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-82b5bd8343188d13 | CVE-2026-9538 | perl-base 5.40.1-6+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-4d4ba11e665ccd08 | CVE-2026-15308 | python3.13 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-d5f854fcea37ee5f | CVE-2026-19445 | python3.13 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-7e85e18c84662ffd | CVE-2026-19553 | python3.13 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-d42c60572856fd5b | CVE-2026-7210 | python3.13 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-af5d8a919ec335f7 | CVE-2026-82049 | python3.13 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-42e431117a3818ba | CVE-2026-15308 | python3.13-minimal 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-476ff9c8404f0550 | CVE-2026-19445 | python3.13-minimal 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-2be373ef0bd8283b | CVE-2026-19553 | python3.13-minimal 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-24739f733c144aa7 | CVE-2026-7210 | python3.13-minimal 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-7cca262f0b6aa3b3 | CVE-2026-82049 | python3.13-minimal 3.13.5-2+deb13u5 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-acf3a2332f175b6c | CVE-2026-16742 | systemd 257.13-1~deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-007174d024bf8903 | CVE-2026-73066 | tesseract-ocr 5.5.0-1+b1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-24ec2b3c21f1e2bd | CVE-2026-88047 | tesseract-ocr 5.5.0-1+b1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-c006a717e7f6f92c | CVE-2026-88048 | tesseract-ocr 5.5.0-1+b1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-c1d8bb680a2e3ed2 | CVE-2026-88051 | tesseract-ocr 5.5.0-1+b1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-49189c2c43b4cf7a | CVE-2026-88052 | tesseract-ocr 5.5.0-1+b1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-e929b3dc8d28b596 | CVE-2026-88053 | tesseract-ocr 5.5.0-1+b1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-2d5aa8e0710d795f | CVE-2026-76642 | util-linux 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-c01e86f56522c7c1 | CVE-2026-78408 | util-linux 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-84e84796576b9751 | CVE-2026-78409 | util-linux 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |
| KB01-SEC-92111b6eedc8d5b9 | CVE-2026-78410 | util-linux 2.41.5-0+deb13u1 | HIGH | PENDING_FORMAL_REVIEW | Vendor fix / reviewed transition; retain sandbox | PENDING |

Critical優先24小時、High72小時是建議的指派後triage SLA；沒有冒填實際責任人、批准期限、延期或risk acceptance。
