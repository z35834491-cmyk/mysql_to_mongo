<template>
  <div class="explain-visualizer">
    <el-empty v-if="!treeData.length" description="暂无可视化执行计划" />
    <el-tree
      v-else
      :data="treeData"
      node-key="id"
      default-expand-all
      :expand-on-click-node="false"
      class="plan-tree"
    >
      <template #default="{ data }">
        <div class="plan-node">
          <span class="node-label">{{ data.label }}</span>
          <span v-if="data.detail" class="node-detail">{{ data.detail }}</span>
        </div>
      </template>
    </el-tree>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  headers?: string[]
  rows?: Record<string, any>[]
}>()

let nodeId = 0
const walk = (value: any, label = 'root'): any => {
  const currentId = ++nodeId
  if (Array.isArray(value)) {
    return {
      id: `${currentId}`,
      label,
      children: value.map((item, index) => walk(item, `${label}[${index}]`))
    }
  }
  if (value && typeof value === 'object') {
    const detail = value.table_name || value.relation_name || value.access_type || value.Node_Type || ''
    return {
      id: `${currentId}`,
      label,
      detail,
      children: Object.entries(value).slice(0, 20).map(([key, child]) => walk(child, key))
    }
  }
  return {
    id: `${currentId}`,
    label,
    detail: String(value ?? '')
  }
}

const treeData = computed(() => {
  nodeId = 0
  const first = props.rows?.[0]
  if (!first) return []
  const candidate = first.EXPLAIN || first['QUERY PLAN'] || first.Plan || first.plan || first
  let parsed = candidate
  if (typeof candidate === 'string') {
    try {
      parsed = JSON.parse(candidate)
    } catch {
      parsed = { text: candidate }
    }
  }
  return [walk(parsed, 'Plan')]
})
</script>

<style scoped>
.explain-visualizer {
  background: #f8fafc;
  border-radius: 10px;
  padding: 8px;
}
.plan-tree {
  background: transparent;
}
.plan-node {
  display: flex;
  align-items: center;
  gap: 8px;
  line-height: 1.6;
}
.node-label {
  font-weight: 600;
  color: #1d2129;
}
.node-detail {
  color: #1677ff;
  font-size: 12px;
}
</style>
