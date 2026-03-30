<template>
  <div class="monaco-wrapper">
    <div ref="containerRef" class="monaco-container"></div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import loader from '@monaco-editor/loader'

const props = withDefaults(defineProps<{
  modelValue: string
  language?: string
  suggestions?: Array<{ label: string; detail?: string; schema?: string; table?: string; column?: string }>
}>(), {
  language: 'sql',
  suggestions: () => []
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'keyword-change', value: string): void
}>()

const containerRef = ref<HTMLElement | null>(null)
let editor: any = null
let monacoRef: any = null
let providerDisposable: any = null
let hoverDisposable: any = null
let changeDisposable: any = null
let resizeObserver: ResizeObserver | null = null

const snippets = [
  { label: 'SELECT 模板', insertText: 'SELECT ${1:*}\\nFROM ${2:table_name}\\nWHERE ${3:condition};', detail: '基础查询模板' },
  { label: 'UPDATE 模板', insertText: 'UPDATE ${1:table_name}\\nSET ${2:column} = ${3:value}\\nWHERE ${4:id} = ${5:1};', detail: '更新模板' },
  { label: 'DELETE 模板', insertText: 'DELETE FROM ${1:table_name}\\nWHERE ${2:id} = ${3:1};', detail: '删除模板' }
]

const applyMarkers = () => {
  if (!monacoRef || !editor) return
  const model = editor.getModel()
  const value = model?.getValue() || ''
  const markers: any[] = []
  const openCount = (value.match(/\(/g) || []).length
  const closeCount = (value.match(/\)/g) || []).length
  if (openCount !== closeCount) {
    markers.push({
      startLineNumber: 1,
      startColumn: 1,
      endLineNumber: 1,
      endColumn: 1,
      message: '括号数量不匹配',
      severity: monacoRef.MarkerSeverity.Error
    })
  }
  if (/^\s*(update|delete)\b/i.test(value) && !/\bwhere\b/i.test(value)) {
    markers.push({
      startLineNumber: 1,
      startColumn: 1,
      endLineNumber: 1,
      endColumn: 1,
      message: 'UPDATE/DELETE 缺少 WHERE 条件',
      severity: monacoRef.MarkerSeverity.Warning
    })
  }
  monacoRef.editor.setModelMarkers(model, 'sql-guard', markers)
}

const registerCompletion = () => {
  if (!monacoRef) return
  if (providerDisposable) {
    providerDisposable.dispose()
  }
  providerDisposable = monacoRef.languages.registerCompletionItemProvider('sql', {
    triggerCharacters: ['.', ' ', '_'],
    provideCompletionItems(model: any, position: any) {
      const word = model.getWordUntilPosition(position)
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn
      }
      return {
        suggestions: [
          ...props.suggestions.map((item) => ({
            label: item.label,
            kind: monacoRef.languages.CompletionItemKind.Field,
            insertText: item.label,
            detail: item.detail || '',
            documentation: item.detail || '',
            range
          })),
          ...snippets.map((item) => ({
            label: item.label,
            kind: monacoRef.languages.CompletionItemKind.Snippet,
            insertText: item.insertText,
            insertTextRules: monacoRef.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            detail: item.detail,
            range
          }))
        ]
      }
    }
  })
  if (hoverDisposable) {
    hoverDisposable.dispose()
  }
  hoverDisposable = monacoRef.languages.registerHoverProvider('sql', {
    provideHover(model: any, position: any) {
      const word = model.getWordAtPosition(position)
      if (!word) return null
      const hit = props.suggestions.find(item => item.label.toLowerCase() === word.word.toLowerCase())
      if (!hit) return null
      return {
        range: new monacoRef.Range(position.lineNumber, word.startColumn, position.lineNumber, word.endColumn),
        contents: [
          { value: `**${hit.label}**` },
          { value: hit.detail || '-' }
        ]
      }
    }
  })
}

onMounted(async () => {
  monacoRef = await loader.init()
  if (!containerRef.value) return
  editor = monacoRef.editor.create(containerRef.value, {
    value: props.modelValue || '',
    language: props.language,
    theme: 'vs-dark',
    automaticLayout: true,
    minimap: { enabled: false },
    fontSize: 13,
    lineNumbersMinChars: 3,
    scrollBeyondLastLine: false,
    wordWrap: 'on',
    tabSize: 2
  })
  changeDisposable = editor.onDidChangeModelContent(() => {
    const value = editor.getValue()
    emit('update:modelValue', value)
    const position = editor.getPosition()
    const model = editor.getModel()
    const word = model?.getWordUntilPosition(position)
    emit('keyword-change', word?.word || '')
    applyMarkers()
  })
  registerCompletion()
  applyMarkers()
  resizeObserver = new ResizeObserver(() => editor?.layout())
  resizeObserver.observe(containerRef.value)
})

watch(() => props.modelValue, (value) => {
  if (!editor) return
  if (editor.getValue() !== value) {
    editor.setValue(value || '')
  }
})

watch(() => props.suggestions, () => {
  registerCompletion()
}, { deep: true })

onBeforeUnmount(() => {
  if (changeDisposable) changeDisposable.dispose()
  if (providerDisposable) providerDisposable.dispose()
  if (hoverDisposable) hoverDisposable.dispose()
  if (resizeObserver) resizeObserver.disconnect()
  if (editor) editor.dispose()
})
</script>

<style scoped>
.monaco-wrapper {
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.monaco-container {
  height: 360px;
  width: 100%;
}
</style>
