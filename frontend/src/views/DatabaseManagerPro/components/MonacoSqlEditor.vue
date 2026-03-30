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
let changeDisposable: any = null
let resizeObserver: ResizeObserver | null = null

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
        suggestions: props.suggestions.map((item) => ({
          label: item.label,
          kind: monacoRef.languages.CompletionItemKind.Field,
          insertText: item.label,
          detail: item.detail || '',
          range
        }))
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
  })
  registerCompletion()
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
