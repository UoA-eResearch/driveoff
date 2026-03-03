import eslint from '@eslint/js';
import eslintConfigPrettier from 'eslint-config-prettier';
import eslintPluginVue from 'eslint-plugin-vue';
import typescriptEslint from 'typescript-eslint';
import { defineConfig } from "eslint/config";

export default defineConfig(
  { ignores: ['*.d.ts', '**/coverage', '**/dist', 'src/client'] },
  {
    extends: [
      eslint.configs.recommended,
      ...typescriptEslint.configs.recommended,
      ...eslintPluginVue.configs['flat/recommended'],
    ],
    files: ['**/*.{ts,vue}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: {
        parser: typescriptEslint.parser,
      },
    },
    rules: {
      // your rules
    },
  },
  eslintConfigPrettier
);