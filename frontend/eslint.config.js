// Configuración de ESLint 9 (formato plano). Reglas esenciales de Vue 3:
// errores reales, no formato, que el equipo no ha acordado todavía.
import pluginVue from 'eslint-plugin-vue'

export default [
  ...pluginVue.configs['flat/essential'],
  {
    files: ['src/**/*.{js,vue}'],
    languageOptions: { ecmaVersion: 2022, sourceType: 'module' }
  }
]
