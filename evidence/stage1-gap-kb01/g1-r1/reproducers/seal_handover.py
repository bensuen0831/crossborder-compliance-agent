import collections,datetime,hashlib,json,pathlib,shutil
from zoneinfo import ZoneInfo
R=pathlib.Path('/workspace/kb01-g1r1');OUT=R/'handover';E=OUT/'evidence/stage1-gap-kb01/g1-r1';D=OUT/'docs/stage1-gap-kb01/g1-r1';S='4593a355d0711a9ba955b1624926a2ec71d60430'
def read(p):return json.loads(p.read_text())
def write(p,d):p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
def cp(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(a,b)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ci=read(R/'ci-complete.json');art=read(R/'artifact-validation.json');reg=read(R/'regression-final.json');assert ci['success_workflows']==12 and ci['verified_job_checkouts']>=22 and art['oci_images_verified']==7
for src,name in [('ci-complete.json','exact_head_ci.json'),('artifact-validation.json','artifact_integrity.json'),('regression-final.json','full_regression.json'),('browser-final-summary.json','browser_validation.json')]:cp(R/src,E/name)
for name in ['collect_ci.py','verify_artifacts.py','measure_final.py','seal_handover.py','collect_browser_log_ids.py']:cp(R/name,E/'reproducers'/name)
# Retain actual full PG reports + mandatory scalar proofs only. Never copy service
# env / persona manifests / unrestricted provider responses from runner artifacts.
allowed={'pytest_full.xml','pytest_full_summary.json','runtime_verify.json','kb01_binary_migration_measured.json','kb01_manifest_migration_measured.json','kb01_taxonomy_migration_measured.json','official-signatures.json','complete.json','backend_measured.json','frontend_measured.json','candidate_frontend_measured.json','stage1_business_browser_measured.json','stage1_business_backend_measured.json','stage1_business_aggregate_measured.json'}
for f in (R/'verified-reports').rglob('*'):
 if f.is_file() and (f.name in allowed or (f.name.endswith('.json') and 'migration' in f.name)):cp(f,E/'verified-reports'/f.relative_to(R/'verified-reports'))
cp(R/'browser-runtime-log-identities.json',E/'browser-runtime-log-identities.json')
local=read(R/'toolchain/provenance.json');prov=[];ret=[]
for t in art['toolchains']:
 name=t['artifact_name'];p=t['provenance'];assert p['security']['high_critical_findings']==135
 prov.append({'artifact_name':name,'base':p['base'],'oci':p['oci'],'source_build':p['source_build'],'sbom':p['sbom'],'security':p['security'],'restore':p['restore'],'all_oci_blobs_verified':True,'packages_match_pinned_local_image':t['packages_match_pinned_local_image'],'critical_binary_hashes_match':t['critical_binary_hashes_match']})
for a in art['artifacts']:
 if a['name'].startswith('toolchain-oci-'):ret.append({k:a[k] for k in ['run_id','id','name','digest','expires_at','downloaded_zip_sha256','oci']})
write(E/'toolchain_identity.json',{'source_sha':S,'base_image_digest':'VERIFIED','apt_provenance':'VERIFIED_SIGNED_SNAPSHOT_PACKAGE_AND_SOURCE_VERSIONS_HASHES','local_actual_provenance':'local-toolchain/provenance.json','ci_images':prov,'short_term_github_artifact_retention':'PASS','artifacts':ret,'long_term_registry_signing_and_retention':'EXTERNAL_DEPENDENCY','local_oci_roundtrip':'PASS','independent_clean_host_restore':'EXTERNAL_DEPENDENCY','build_reproducibility_claim':'Pinned source universe and matching installed-package/critical-executable hashes; OCI build timestamps/config identities may differ. No false bit-for-bit all-build claim.'})
write(E/'sbom_validation.json',{'source_sha':S,'decision':'PASS','standard':'SPDX-2.3','official_schema':local['sbom'],'local_packages':290,'ci_images':[{'artifact_name':t['artifact_name'],'sbom':t['provenance']['sbom'],'oci_manifest_digest':t['provenance']['oci']['manifest_digest'],'package_inventory_matches_local':t['packages_match_pinned_local_image']} for t in art['toolchains']],'critical_executable_count':10,'parser_sources_and_containerfile':'Per actual image source_build hashes; no reuse of old G0 image SBOM.'})
p=E/'security_validation.json';sec=read(p);sec['runtime_sandbox_regression']='PASS_ACTUAL_FRESH_SOURCE_FULL_AND_KB_FOCUSED_POSTGRES_AND_BROWSER';sec['ci_image_severity_counts']=[{'artifact_name':t['artifact_name'],'counts':t['provenance']['security']['severities'],'report_sha256':t['provenance']['security']['report_sha256']} for t in art['toolchains']];write(p,sec)
kb=read(R/'verified-reports/12404610600/complete.json');write(E/'capacity_validation.json',{'source_sha':S,**{k:kb[k] for k in ['decision','runner_checkout_shas','capacity','browser_retries']}})
subsets=[{'run_id':r['id'],'job_id':j['id'],'source_sha':j['runner_checkout_sha'],'summaries':j['observed_test_summary_counts']} for r in ci['runs'] for j in r['jobs'] if j['name']=='contract-tests'];write(E/'supplemental_contract_subsets.json',{'classification':'SUPPLEMENTAL_SELECTED_CONTRACT_SUBSET_NOT_COMPLETE_POSTGRES_SUITE','executions':subsets,'full_pg_zero_skips_and_deselections_verified_separately':True})
readiness={'source_sha':S,'observed_at':datetime.datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'n_plus_one_fix':'PASS','toolchain_reproducibility_controls':'PASS_WITH_DISCLOSED_EXTERNAL_LONG_TERM_RETENTION_AND_CLEAN_HOST_RESTORE_DEPENDENCIES','scan_execution':'PASS','security_acceptance':'BLOCKED_REVIEW_REQUIRED','technical_uat_candidate':'READY','candidate_scope':'LOCAL_ISOLATED_SYNTHETIC_TECHNICAL_FUNCTIONAL_TESTING_ONLY','rc1_technical_acceptance':'BLOCKED','blockers':['Unapproved 134 HIGH +1 CRITICAL package findings (44 distinct HIGH/CRITICAL CVE IDs) in actual fixed toolchain; no authorized security risk acceptance.'],'functional_regression':'PASS','full_pg_passed':reg['backend_passed'],'architecture_passed':456,'runtime_passed':25,'frontend_passed':180,'browser_passed':89,'browser_retries':0,'mandatory_ci_success':12,'actual_job_checkout_matches':ci['verified_job_checkouts'],'reviewer_approval':'PENDING','master_full_text_reconciliation':'INPUT_REQUIRED','formal_requirement_change_approval':'NOT_VERIFIED','kb01_f1':'BLOCKED_EXTERNAL_EVIDENCE_PENDING','legal_l2':'NOT_ACCEPTED','production_deployment':'NOT_ACCEPTED','paid_internet_llm':'NOT_EXECUTED','real_regulatory_acceptance':'NOT_EXECUTED','production_uat':'NOT_EXECUTED','pr29':'OPEN_DRAFT_NOT_MERGED','main_merge':'NOT_AUTHORIZED','release_tag':'UNCHANGED','stage2':'NOT_STARTED'};write(E/'rc1_readiness.json',readiness)
# All prose is generated from measured evidence above, not prospective PASS.
footer='\n\nPR29 保持 Draft／未合併；Main060cbb5與 v3.7-stage1-e2e-pass 不變。Formal Reviewer Approval=PENDING；MASTER full-text reconciliation=INPUT_REQUIRED；Formal requirement change approval=NOT_VERIFIED。KB01-F1=BLOCKED_EXTERNAL_EVIDENCE_PENDING，LEGAL L2／Production Deployment=NOT ACCEPTED；Real Regulatory Acceptance／Production UAT／Paid Internet LLM=NOT EXECUTED；Stage2=NOT STARTED。\n'
(D/'medium_001_fix_report.md').write_text('''# KB01-G0-001 修復結果

N_PLUS_ONE_FIX = PASS。沿用既有 list owner、COUNT／filters／排序／分頁，selected versions、creator、latest actor 改三次 tenant-bound batch read，非空頁固定5SQL；空頁2SQL。ACTIVE 仍取 exact active_version_id；非 ACTIVE 取最高version_no；沒有跨租戶 cache 或第二 Metadata SoT。

真正 PostgreSQL，同一資料與連線環境，以 `git show 39c3581...:knowledge_taxonomy.py` 的舊 reader 作獨立測試 oracle，DRAFT/ACTIVE/MIXED × page1/4/25/100完整JSON相等；三locale、缺actor/version、租戶隔離、權限、exact-active不被較新draft覆蓋均有回歸。既有30＋新增7 taxonomy tests=37PASS。

額外實證舊enabled-filter在多draft時丟失correlation而CardinalityViolation。最小修復重用tenant-bound selected-version expression，保持 intended enabled semantics；該原本失敗請求的修復獨立列出，未冒稱可以對不存在的舊response作parity。

ACTIVE100，3次paired讀取中位：402→5 SQL，2.627473→0.036336秒。全部12個頁面／lifecycle組合與完整response SHA256見 taxonomy_performance.json／taxonomy_response_parity.json。這是隔離PG測量，非生產SLA。

'''+f'實際測試產品 `{S}`；完整新Head回歸與actual jobcheckout封存於本獨立evidence。'+footer)
p=read(R/'paired-performance-final.json');rows=['| Lifecycle | Rows | Before SQL | After SQL | Before median s | After median s |','|---|---:|---:|---:|---:|---:|']
for v in p['samples']:rows.append(f"| {v['lifecycle']} | {v['page_size']} | {v['before_sql']} | {v['after_sql']} | {v['before_median_seconds']:.6f} | {v['after_median_seconds']:.6f} |")
(D/'performance_comparison.md').write_text('# 同環境 PostgreSQL paired comparison\n\n每個case相同資料/engine，舊新reader各3次讀取，保留每次wall time及SQL count；未mock SQL計數。完整JSON逐次相等，digest保存。\n\n'+'\n'.join(rows)+'\n\nG1既有2.536919秒是不同session的歷史測量，未拿它計算同環境加速比。舊查詢依page行數線性增加，新查詢非空頁固定5SQL；沒有把計數查詢或授權／actor讀取排除。'+footer)
(D/'medium_002_fix_report.md').write_text('''# KB01-G0-002 修復及剩餘處置

已修復 floating base/APT universe 與 CI映像 provenance 缺口。linux/amd64 Debian base `sha256:4876fdea29cac1a33a3195f1eb1952feb1fca7dd6dd00be3e2f1879cf20d34d2` 已核對實際manifest/config；Debian+security snapshot20261021T000000Z，HTTPS／signed InRelease／index／.deb hashes／package/source version 保存。只關閉 historical snapshot Valid-Until，未關閉GPG/TLS。

新實際映像290個installed packages、10個critical executable hashes、五個parser source hashes、Containerfile/inventory helper hashes均綁實際OCI identity。SPDX2.3通過固定官方schema。七個新CI image獨立生成provenance/SBOM/scan/OCI archive，逐一驗ZIP digest及所有OCI blobs，package inventory及關鍵工具hash均與固定來源本機映像一致。Docker config ID、OCI manifest、archive hash、GitHub ZIP digest各自記錄，不互換。

GitHub七份實際Archive均已下載驗證，可在到期前重取；API顯示expires_at=2027-01-20T05:23:24Z。這是短期artifact retention，不是長期registry、簽署或獨立clean-host還原。Local OCI roundtrip PASS；long-term retention／clean-host restore=EXTERNAL_DEPENDENCY。

掃描執行 PASS，但 security acceptance=BLOCKED_REVIEW_REQUIRED：實際每份映像 LOW302/MEDIUM250/HIGH134/CRITICAL1/UNKNOWN5，共692個package findings；HIGH/CRITICAL合計44個不同CVE。Critical CVE-2026-6653/libxml2 未回報FixedVersion。這不是已證實可利用性，亦不能推定可接受風險；沒有隱藏unfixed、抑制finding或冒簽risk acceptance。

Network isolation/non-root/read-only/drop capabilities/resource limits/malware scan/archive sandbox維持；新映像重新通過parser、RAR4/RAR5/ZIP、容量及安全回歸。Official CVD main/daily/bytecode的hash與ClamAV engine/executable各自保存。

Formal Security Reviewer仍須評估可達性與處置。若要求依賴更新，須最小新產品commit與完整新exact-head gate；不能以本次成功測試取代新source證據。Medium重現性修復已完成，最終安全批准未完成。
'''+footer)
(D/'toolchain_provenance.md').write_text((D/'medium_002_fix_report.md').read_text().replace('# KB01-G0-002 修復及剩餘處置','# 實際工具映像與供應鏈證據')+'\n實際檔案：`toolchain_identity.json`，`sbom_validation.json`，`security_validation.json`，`artifact_integrity.json`，`local-toolchain/*`。原始完整Trivy報告與本機SPDX均保存；CI每個報告SHA256與artifact/member digest可反查。`source_identity.json`記錄739個source/test/fixture hashes。\n')
(D/'technical_uat_release_notes.md').write_text(f'''# KB01-Technical-UAT-RC1

TECHNICAL_UAT_CANDIDATE = READY（僅限隔離合成資料功能測試）\nRC1_TECHNICAL_ACCEPTANCE = BLOCKED — SECURITY_REVIEW_PENDING

產品 `{S}`，既有PR29產品分支。Linux/amd64已實測，Python3.12.14/Node24.19.0/PostgreSQL17.11+pgvector0.8.7/Redis7.4.11，migration0024。未驗證Windows原生/WSL，不宣稱已支援。

Start/Stop/Health/Demo/Logs/Diagnose/Reset沿用既有UAT Host、React、canonical知識服務及workers。AUTHOR/REVIEWER/PUBLISHER/RESTRICTED為不同actor/permissions；不提供production身份。100個ACTIVE分類與18個六格式原檔已實際stop/start保留exact bytes/hash；另以一次性Dockerresources實測Reset只清exact owned containers/volumes，原檔封存與獨立volume保留。

操作指南：`../uat/RC1_quick_start.md`、installation、user_test_cases、roles、known_limitations、troubleshooting、feedback_template。前端 `http://127.0.0.1:15173/admin?admin_resource=knowledge-management`；backend `http://127.0.0.1:18010/health/live`，本輪兩者實際200。Loopback只屬執行命令那台電腦；沒有公開Cloud URL或持續託管承諾。請依固定SHA clone本機執行，不可暴露synthetic login到Internet。

定向PG320PASS保留原303+17新增，完整遠端PG {reg['backend_passed']}PASS保留原1315；architecture456/456，runtime25/25，frontend180，browser89/89（原88+角色切換1），retries0。12/12 mandatory workflows SUCCESS；{ci['verified_job_checkouts']}/{ci['verified_job_checkouts']} actual jobcheckout MATCH。全量PG無failed/errors/skipped/deselected；supplemental contract選取另外披露。

Security scan有134High+1Critical待正式處置，不能宣稱RC1整體安全接受。UAT01–18的人類結果保持Pending，工程自動化不代替Production UAT或法律審核。
'''+footer)
(D/'final_technical_acceptance.md').write_text(f'''# KB01-G1-R1 最終技術交付

N_PLUS_ONE_FIX = PASS\nTOOLCHAIN_REPRODUCIBILITY_CONTROLS = PASS（外部保存／clean-host依賴另列）\nTECHNICAL_UAT_CANDIDATE = READY — LOCAL / ISOLATED SYNTHETIC TECHNICAL TESTING ONLY\nFUNCTIONAL_REGRESSION = PASS\nRC1_TECHNICAL_ACCEPTANCE = BLOCKED — SECURITY_REVIEW_PENDING

| 新exact產品Head Gate | 實測 |
|---|---|
| Source | `{S}` |
| Full PostgreSQL | {reg['backend_passed']}PASS，4個獨立CI執行 |
| Failed / errors / skipped / deselected | 0/0/0/0 |
| 原完整backend IDs / 新增 | 1315全部保留 / {reg['backend_passed']-1315} |
| Local directed PG | 320PASS=303原用例+17新增 |
| Architecture | 456/456PASS |
| Runtime | 25/25PASS |
| Frontend | 180PASS |
| Typecheck/lint/build/i18n | PASS |
| Browser | 89/89PASS=88原必跑+1RC1角色 |
| Browser retries | 0 |
| Mandatory CI | 12/12SUCCESS |
| Actual checkout | {ci['verified_job_checkouts']}/{ci['verified_job_checkouts']}MATCH |
| Source/test/fixture hashes | 739 verified |
| Artifact ZIP / OCI image | {art['artifact_zip_digests_verified']} /7 verified |
| Alembic | 0024唯一head，0001–0024 byte unchanged |

**阻塞項：** 固定實際工具映像134High+1Critical package findings尚無正式批准處置。Trivy scan execution PASS不等於security acceptance PASS；未冒簽review或risk acceptance。已交付能啟動及操作的隔離技術候選，不能宣稱整體RC1驗收、正式部署或法律接受PASS。

已完成兩項程式修復；安全Reviewer需確認依賴漏洞的修復／風險處置。長期registry/簽署/保存與獨立clean-host restore=EXTERNAL_DEPENDENCY；GitHub短期OCI artifact已真實保存驗證。MASTER原文及指定正式Reviewer仍待提供，不重複推定批准。

CI/source/log/artifact/test IDs與safe hashes見 `evidence/stage1-gap-kb01/g1-r1/`。本文件在獨立evidence branch封存，不推進產品Head/Main；完整CI只對上面產品SHA成立。舊source50/04的CI取消與local全套143終止被保留為superseded development，未借用PASS。曾有scanner掛載路徑及CI fixture少一case兩項開發失敗，均最小修正後對新459重新跑12個workflows；未加browser retry／刪除skip或弱化assertion。
'''+footer+'\n補充contract-tests子集的實際 skipped/deselected 數見 `supplemental_contract_subsets.json`，與四個完整PG suite分開，沒有冒稱subset為全量。\n')
# Hash complete evidence tree excluding this self-referential index.
hashes={str(p.relative_to(OUT)):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='evidence_digests.json'};write(E/'evidence_digests.json',{'algorithm':'SHA256','tested_product_sha':S,'scope':'All safe handover documentation/evidence except this index; independent evidence commit is not a product baseline.','files':hashes,'file_count':len(hashes)})
print('Sealed independent handover',len(hashes),'files')
