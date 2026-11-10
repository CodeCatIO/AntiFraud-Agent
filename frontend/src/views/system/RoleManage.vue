<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Edit, Delete, Setting } from '@element-plus/icons-vue'

// ---------- Mock 数据（接口通了以后删除） ----------
let mockRoleId = 4
const mockRoles = [
  {
    id: 1,
    name: '管理员',
    flag: 'ADMIN',
    description: '系统管理员，拥有全部权限',
    menuIds: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
  },
  {
    id: 2,
    name: '普通用户',
    flag: 'USER',
    description: '普通用户，可使用检测和存证功能',
    menuIds: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
  },
  {
    id: 3,
    name: '访客',
    flag: 'GUEST',
    description: '访客角色，仅可查看仪表盘',
    menuIds: [1],
  },
]

// Mock 菜单树（与 MenuManage 的菜单数据一致）
const mockMenuTree = [
  { id: 1, label: '仪表盘' },
  {
    id: 2,
    label: '多模态检测',
    children: [
      { id: 3, label: '文本检测' },
      { id: 4, label: '语音检测' },
      { id: 5, label: '图片检测' },
    ],
  },
  { id: 6, label: '检测记录' },
  { id: 7, label: '区块链存证' },
  { id: 8, label: '水印工具' },
  {
    id: 9,
    label: '个人中心',
    children: [
      { id: 10, label: '个人信息' },
      { id: 11, label: '修改密码' },
    ],
  },
  {
    id: 12,
    label: '系统管理',
    children: [
      { id: 13, label: '用户管理' },
      { id: 14, label: '角色管理' },
      { id: 15, label: '菜单管理' },
    ],
  },
]

const roles = ref([])
const loading = ref(false)

// ---------- 加载角色列表 ----------
async function loadRoles() {
  loading.value = true
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // const res = await getRoleList()
    // roles.value = res || []
    await new Promise((resolve) => setTimeout(resolve, 300))
    roles.value = [...mockRoles]
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    loading.value = false
  }
}

// ---------- 新增/编辑弹窗 ----------
const dialogVisible = ref(false)
const isEdit = ref(false)
const dialogTitle = computed(() => (isEdit.value ? '编辑角色' : '新增角色'))
const submitting = ref(false)
const formRef = ref(null)

const form = reactive({
  id: null,
  name: '',
  flag: '',
  description: '',
})

const rules = {
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
  flag: [
    { required: true, message: '请输入角色标识', trigger: 'blur' },
    { pattern: /^[A-Z]+$/, message: '角色标识必须为大写英文', trigger: 'blur' },
  ],
}

function openCreate() {
  isEdit.value = false
  Object.assign(form, { id: null, name: '', flag: '', description: '' })
  dialogVisible.value = true
}

function openEdit(row) {
  isEdit.value = true
  Object.assign(form, { id: row.id, name: row.name, flag: row.flag, description: row.description })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // if (isEdit.value) {
    //   await updateRole(form.id, { ...form })
    // } else {
    //   await createRole({ ...form })
    // }
    await new Promise((resolve) => setTimeout(resolve, 500))

    if (isEdit.value) {
      const target = mockRoles.find((item) => item.id === form.id)
      if (target) Object.assign(target, { ...form })
      ElMessage.success('编辑成功')
    } else {
      mockRoles.push({
        id: mockRoleId++,
        name: form.name,
        flag: form.flag,
        description: form.description,
        menuIds: [],
      })
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    loadRoles()
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    submitting.value = false
  }
}

// ---------- 删除 ----------
async function handleDelete(row) {
  // 接口未通前用 Mock 占位，接口通了以后替换为：
  // await deleteRole(row.id)
  await new Promise((resolve) => setTimeout(resolve, 300))
  const idx = mockRoles.findIndex((item) => item.id === row.id)
  if (idx > -1) mockRoles.splice(idx, 1)
  ElMessage.success('删除成功')
  loadRoles()
}

// ---------- 分配菜单弹窗 ----------
const menuDialogVisible = ref(false)
const menuSubmitting = ref(false)
const treeRef = ref(null)
const roleForm = reactive({ roleId: null, roleName: '' })

function openAssignMenu(row) {
  roleForm.roleId = row.id
  roleForm.roleName = row.name
  menuDialogVisible.value = true
  // 弹窗渲染后设置该角色已有菜单为默认勾选
  setTimeout(() => {
    treeRef.value?.setCheckedKeys(row.menuIds || [], false)
  })
}

async function handleAssignMenu() {
  menuSubmitting.value = true
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // const menuIds = [
    //   ...treeRef.value.getCheckedKeys(),
    //   ...treeRef.value.getHalfCheckedKeys(),
    // ]
    // await assignMenus({ roleId: roleForm.roleId, menuIds })
    await new Promise((resolve) => setTimeout(resolve, 500))

    const checkedKeys = [
      ...treeRef.value.getCheckedKeys(),
      ...treeRef.value.getHalfCheckedKeys(),
    ]
    const target = mockRoles.find((item) => item.id === roleForm.roleId)
    if (target) target.menuIds = checkedKeys
    ElMessage.success('菜单分配成功')
    menuDialogVisible.value = false
    loadRoles()
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    menuSubmitting.value = false
  }
}

onMounted(loadRoles)
</script>

<template>
  <div class="role-manage">
    <!-- 顶部操作栏 -->
    <el-card shadow="hover" class="toolbar-card">
      <el-button type="primary" :icon="Plus" @click="openCreate">新增角色</el-button>
    </el-card>

    <!-- 角色列表 -->
    <el-card shadow="hover">
      <el-table :data="roles" v-loading="loading" stripe border>
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="name" label="角色名称" width="140" />
        <el-table-column label="角色标识" width="140">
          <template #default="{ row }">
            <code class="flag-text">{{ row.flag }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="240" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="openEdit(row)">编辑</el-button>
            <el-button type="warning" link :icon="Setting" @click="openAssignMenu(row)">
              分配菜单
            </el-button>
            <el-popconfirm title="确定删除该角色吗？" @confirm="handleDelete(row)">
              <template #reference>
                <el-button type="danger" link :icon="Delete">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入角色名称" maxlength="20" />
        </el-form-item>
        <el-form-item label="角色标识" prop="flag">
          <el-input v-model="form.flag" placeholder="请输入角色标识（大写英文，如 ADMIN）" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="请输入角色描述"
            maxlength="100"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 分配菜单弹窗 -->
    <el-dialog
      v-model="menuDialogVisible"
      :title="`分配菜单 - ${roleForm.roleName}`"
      width="420px"
      destroy-on-close
    >
      <el-tree
        ref="treeRef"
        :data="mockMenuTree"
        node-key="id"
        show-checkbox
        check-strictly
        default-expand-all
        :props="{ label: 'label', children: 'children' }"
      />
      <template #footer>
        <el-button @click="menuDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="menuSubmitting" @click="handleAssignMenu">
          确认分配
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.role-manage {
  .toolbar-card {
    margin-bottom: 16px;
  }

  .flag-text {
    font-family: Consolas, Monaco, 'Courier New', monospace;
    font-size: 13px;
    color: #409eff;
  }
}
</style>
