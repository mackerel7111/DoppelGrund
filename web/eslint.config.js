import pluginVue from 'eslint-plugin-vue';
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript';
import prettierConfig from 'eslint-config-prettier';

export default defineConfigWithVueTs(
  { ignores: ['dist/**', 'node_modules/**', 'public/**', 'coverage/**'] },
  pluginVue.configs['flat/recommended'],
  vueTsConfigs.strict,
  {
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      // component names are fixed by structure.md (Scorecard, Shortlist, …)
      'vue/multi-word-component-names': 'off',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
  prettierConfig,
);
