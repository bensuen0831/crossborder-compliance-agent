# Frontend dependency integration result

Canonical dependencies, devDependencies and engines remain identical to tested C SHA 3f89f1e8f16402f4754b474260cb9022a4bf92c6; frontend/package-lock.json remains byte-identical. frontend/package.json adds only the check:i18n script and its mandatory pre-build invocation; declared dependency versions do not change. No new dependency, unrelated upgrade or silent major-version change was performed on C. All D runtime/test dependencies already exist in C; D modules were checked against the existing C toolchain. D's separate lockfile and package were removed, rather than combined. The original D dependency tree remains recoverable from its source SHA.

Where C and D had different development-tool majors (Vite/plugin, hooks lint, jsdom, Vitest), the final versions are the pre-existing C versions, validated by the moved D tests, canonical lint and production build.

| Dependency | C declaration | D declaration | Final locked version | Deduplicated | Reason |
|---|---|---|---|---|---|
| @ant-design/icons | ^6.1.0 | — | 6.3.4 | C only | Retain tested C lock/toolchain |
| @tanstack/react-query | ^5.90.0 | — | 5.104.1 | C only | Retain tested C lock/toolchain |
| ajv | ^8.17.1 | — | 8.20.0 | C only | Retain tested C lock/toolchain |
| ajv-formats | ^3.0.1 | — | 3.0.1 | C only | Retain tested C lock/toolchain |
| antd | ^6.0.0 | — | 6.6.5 | C only | Retain tested C lock/toolchain |
| i18next | ^25.6.0 | — | 25.10.10 | C only | Retain tested C lock/toolchain |
| react | ^19.2.0 | ^19.1.0 | 19.3.0 | Yes: canonical C copy | Retain tested C lock/toolchain |
| react-dom | ^19.2.0 | ^19.1.0 | 19.3.0 | Yes: canonical C copy | Retain tested C lock/toolchain |
| react-i18next | ^16.2.0 | — | 16.6.6 | C only | Retain tested C lock/toolchain |
| react-router-dom | ^7.9.0 | — | 7.18.4 | C only | Retain tested C lock/toolchain |
| @eslint/js | ^9.39.0 | ^9.0.0 | 9.39.5 | Yes: canonical C copy | Retain tested C lock/toolchain |
| @playwright/test | ^1.56.0 | — | 1.63.0 | C only | Retain tested C lock/toolchain |
| @testing-library/jest-dom | ^6.9.0 | ^6.6.0 | 6.9.1 | Yes: canonical C copy | Retain tested C lock/toolchain |
| @testing-library/react | ^16.3.0 | ^16.3.0 | 16.3.3 | Yes: canonical C copy | Retain tested C lock/toolchain |
| @testing-library/user-event | ^14.6.0 | ^14.6.0 | 14.6.7 | Yes: canonical C copy | Retain tested C lock/toolchain |
| @types/node | ^24.10.0 | — | 24.19.1 | C only | Retain tested C lock/toolchain |
| @types/react | ^19.2.0 | ^19.1.0 | 19.3.0 | Yes: canonical C copy | Retain tested C lock/toolchain |
| @types/react-dom | ^19.2.0 | ^19.1.0 | 19.3.0 | Yes: canonical C copy | Retain tested C lock/toolchain |
| @vitejs/plugin-react | ^5.1.0 | ^4.5.0 | 5.2.0 | Yes: canonical C copy | Retain tested C lock/toolchain |
| eslint | ^9.39.0 | ^9.0.0 | 9.39.5 | Yes: canonical C copy | Retain tested C lock/toolchain |
| eslint-plugin-react-hooks | ^7.0.0 | ^5.2.0 | 7.1.1 | Yes: canonical C copy | Retain tested C lock/toolchain |
| eslint-plugin-react-refresh | ^0.4.24 | — | 0.4.26 | C only | Retain tested C lock/toolchain |
| globals | ^16.5.0 | — | 16.5.0 | C only | Retain tested C lock/toolchain |
| jsdom | ^27.2.0 | ^26.1.0 | 27.4.0 | Yes: canonical C copy | Retain tested C lock/toolchain |
| openapi-typescript | ^7.10.0 | — | 7.13.0 | C only | Retain tested C lock/toolchain |
| typescript | ^5.9.3 | ^5.8.0 | 5.9.3 | Yes: canonical C copy | Retain tested C lock/toolchain |
| typescript-eslint | ^8.46.0 | ^8.0.0 | 8.71.0 | Yes: canonical C copy | Retain tested C lock/toolchain |
| vite | ^7.2.0 | ^6.3.0 | 7.3.6 | Yes: canonical C copy | Retain tested C lock/toolchain |
| vitest | ^4.0.0 | ^3.2.0 | 4.1.11 | Yes: canonical C copy | Retain tested C lock/toolchain |

Final: one production package.json, one lockfile, one Vite build and one React root. npm ci and frozen API/type regeneration pass without lock/generated-file drift. The catalog checker uses the existing TypeScript dependency and Node built-ins; no additional production or development dependency is introduced.
