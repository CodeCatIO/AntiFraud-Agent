<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'

// ---------- Mock 菜单数据（与 Aside.vue 的菜单对应，接口通了以后删除） ----------
let mockMenuId = 16
const mockMenus = [
  { id: 1, name: '仪表盘', path: '/dashboard', icon: 'Odometer', sort: 1, type: 'menu', parentId: null },
  { id: 2, name: '多模态检测', path: '/detect', icon: 'Monitor', sort: 2, type: 'dir', parentId: null },
  { id: 3, name: '文本检测', path: '/detect/text', icon: 'Document', sort: 1, type: 'menu', parentId: 2 },
  { id: 4, name: '语音检测', path: '/detect/voice', icon: 'Microphone', sort: 2, type: 'menu', parentId: 2 },
  { id: 5, name: '图片检测', path: '/detect/image', icon: 'Picture', sort: 3, type: 'menu', parentId: 2 },
  { id: 6, name: '检测记录', path: '/records', icon: 'List', sort: 3, type: 'menu', parentId: null },
  { id: 7, name: '区块链存证', path: '/blockchain', icon: 'Link', sort: 4, type: 'menu', parentId: null },
  { id: 8, name: '水印工具', path: '/watermark', icon: 'Stamp', sort: 5, type: 'menu', parentId: null },
  { id: 9, name: '个人中心', path: '/profile', icon: 'UserFilled', sort: 6, type: 'dir', parentId: null },
  { id: 10, name: '个人信息', path: '/profile', icon: 'UserFilled', sort: 1, type: 'menu', parentId: 9 },
  { id: 11, name: '修改密码', path: '/password', icon: 'Key', sort: 2, type: 'menu', parentId: 9 },
  { id: 12, name: '系统管理', path: '/system', icon: 'Setting', sort: 7, type: 'dir', parentId: null },
  { id: 13, name: '用户管理', path: '/system/user', icon: 'User', sort: 1, type: 'menu', parentId: 12 },
  { id: 14, name: '角色管理', path: '/system/role', icon: 'Avatar', sort: 2, type: 'menu', parentId: 12 },
  { id: 15, name: '菜单管理', path: '/system/menu', icon: 'Menu', sort: 3, type: 'menu', parentId: 12 },
]

// 图标名选项（Element Plus 图标名，与路由 meta.icon 风格一致）
const iconOptions = [
  'Odometer', 'Monitor', 'Document', 'Microphone', 'Picture', 'List',
  'Link', 'Stamp', 'UserFilled', 'Key', 'Setting', 'User', 'Avatar',
  'Menu', 'Lock', 'Bell', 'Search', 'Delete',
]

const menus = ref([])
const loading = ref(false)

// ---------- 树形数据：parentId → children ----------
function buildTree(list) {
  const map = {}
  const roots = []
  list.forEach((item) => {
    map[item.id] = { ...item, children: [] }
  })
  list.forEach((item) => {
    if (item.parentId && map[item.parentId]) {
      map[item.parentId].children.push(map[item.id])
    } else {
      roots.push(map[item.id])
    }
  })
  // 去掉空 children，避免树形表格出现展开箭头
  Object.values(map).forEach((item) => {
    if (!item.children.length) delete item.children
  })
  return roots
}

const treeData = computed(() => buildTree(menus.value))

// 父菜单选项（仅目录类型可作为父级，且排除自身，避免循环嵌套）
const parentOptions = computed(() =>
  menus.value.filter((item) => item.type === 'dir' && item.id !== form.id)
)

// ---------- 加载菜单列表 ----------
async function loadMenus() {
  loading.value = true
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // const res = await getMenuList()
    // menus.value = res || []
    await new Promise((resolve) => setTimeout(resolve, 300))
    menus.value = [...mockMenus]
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    loading.value = false
  }
}

// ---------- 新增/编辑弹窗 ----------
const dialogVisible = ref(false)
const isEdit = ref(false)
const dialogTitle = computed(() => (isEdit.value ? '编辑菜单' : '新增菜单'))
const submitting = ref(false)
const formRef = ref(null)

const form = reactive({
  id: null,
  name: '',
  path: '',
  icon: '',
  sort: 1,
  type: 'menu',
  parentId: null,
})

const rules = {
  name: [{ required: true, message: '请输入菜单名称', trigger: 'blur' }],
  path: [{ required: true, message: '请输入路由路径', trigger: 'blur' }],
}

function openCreate(parentId = null) {
  isEdit.value = false
  Object.assign(form, { id: null, name: '', path: '', icon: '', sort: 1, type: 'menu', parentId })
  dialogVisible.value = true
}

function openEdit(row) {
  isEdit.value = true
  Object.assign(form, {
    id: row.id,
    name: row.name,
    path: row.path,
    icon: row.icon,
    sort: row.sort,
    type: row.type,
    parentId: row.parentId,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // if (isEdit.value) {
    //   await updateMenu(form.id, { ...form })
    // } else {
    //   await createMenu({ ...form })
    // }
    await new Promise((resolve) => setTimeout(resolve, 500))

    if (isEdit.value) {
      const target = mockMenus.find((item) => item.id === form.id)
      if (target) Object.assign(target, { ...form })
      ElMessage.success('编辑成功')
    } else {
      mockMenus.push({ id: mockMenuId++, ...form })
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    loadMenus()
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    submitting.value = false
  }
}

// ---------- 删除 ----------
async function handleDelete(row) {
  // 有子菜单时不允许删除
  if (menus.value.some((item) => item.parentId === row.id)) {
    ElMessage.warning('该菜单包含子菜单，请先删除子菜单')
    return
  }
  // 接口未通前用 Mock 占位，接口通了以后替换为：
  // await deleteMenu(row.id)
  await new Promise((resolve) => setTimeout(resolve, 300))
  const idx = mockMenus.findIndex((item) => item.id === row.id)
  if (idx > -1) mockMenus.splice(idx, 1)
  ElMessage.success('删除成功')
  loadMenus()
}

onMounted(loadMenus)
</script>

<template>
  <div class="menu-manage">
    <!-- 顶部操作栏 -->
    <el-card shadow="hover" class="toolbar-card">
      <el-button type="primary" :icon="Plus" @click="openCreate(null)">新增菜单</el-button>
    </el-card>

    <!-- 树形表格 -->
    <el-card shadow="hover">
      <el-table
        :data="treeData"
        v-loading="loading"
        row-key="id"
        :tree-props="{ children: 'children' }"
        default-expand-all
        stripe
        border
      >
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="name" label="菜单名称" width="200" />
        <el-table-column prop="path" label="路由路径" min-width="160" />
        <el-table-column prop="icon" label="图标" width="140" align="center">
          <template #default="{ row }">
            <code class="icon-text">{{ row.icon || '-' }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="sort" label="排序号" width="90" align="center" />
        <el-table-column label="类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.type === 'dir' ? 'warning' : 'primary'">
              {{ row.type === 'dir' ? '目录' : '菜单' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.type === 'dir'"
              type="primary"
              link
              :icon="Plus"
              @click="openCreate(row.id)"
            >
              新增子项
            </el-button>
            <el-button type="primary" link :icon="Edit" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确定删除该菜单吗？" @confirm="handleDelete(row)">
              <template #reference>
                <el-button type="danger" link :icon="Delete">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="菜单名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入菜单名称" maxlength="20" />
        </el-form-item>
        <el-form-item label="路由路径" prop="path">
          <el-input v-model="form.path" placeholder="如 /system/user" />
        </el-form-item>
        <el-form-item label="图标">
          <el-select v-model="form.icon" placeholder="请选择图标" clearable filterable style="width: 100%">
            <el-option v-for="icon in iconOptions" :key="icon" :label="icon" :value="icon" />
          </el-select>
        </el-form-item>
        <el-form-item label="父菜单">
          <el-select
            v-model="form.parentId"
            placeholder="顶级菜单（不选则为顶级）"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="item in parentOptions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="排序号">
          <el-input-number v-model="form.sort" :min="1" :max="999" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.type">
            <el-radio value="dir">目录</el-radio>
            <el-radio value="menu">菜单</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.menu-manage {
  .toolbar-card {
    margin-bottom: 16px;
  }

  .icon-text {
    font-family: Consolas, Monaco, 'Courier New', monospace;
    font-size: 13px;
    color: #409eff;
  }
}
</style>
