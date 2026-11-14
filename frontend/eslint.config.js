import vueI18n from '@intlify/eslint-plugin-vue-i18n'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'

export default defineConfigWithVueTs(
  { ignores: ['dist/**', 'node_modules/**', 'src/api/schema.d.ts', 'coverage/**'] },
  pluginVue.configs['flat/recommended'],
  vueTsConfigs.recommended,
  ...vueI18n.configs.recommended,
  {
    settings: {
      'vue-i18n': {
        // One file per module per locale; each file's top-level key is its namespace
        // (locales/en/auth.json → {"auth": {...}}), so keys read `auth.sign_in` everywhere.
        localeDir: './src/locales/*/*.json',
        messageSyntaxVersion: '^11.0.0',
      },
    },
    rules: {
      // §10.4: no hard-coded UI strings; every text comes from vue-i18n.
      '@intlify/vue-i18n/no-raw-text': [
        'error',
        { ignorePattern: '^[-#:()&|/.,…%+·•×—–0-9\\s]+$', ignoreText: ['EasyDeploy', 'API', 'TOTP'] },
      ],
      '@intlify/vue-i18n/no-missing-keys': 'error',
      '@intlify/vue-i18n/no-unused-keys': 'off',
      '@intlify/vue-i18n/no-dynamic-keys': 'off',
      '@intlify/vue-i18n/no-v-html': 'error',
      'vue/multi-word-component-names': 'off',
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/html-self-closing': 'off',
      'vue/html-indent': 'off',
      'vue/html-closing-bracket-newline': 'off',
      'vue/multiline-html-element-content-newline': 'off',
    },
  },
  {
    files: ['**/*.spec.ts'],
    rules: { '@intlify/vue-i18n/no-raw-text': 'off' },
  },
)
