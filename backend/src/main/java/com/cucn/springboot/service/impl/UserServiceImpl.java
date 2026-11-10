package com.cucn.springboot.service.impl;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.log.Log;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.cucn.springboot.controller.dto.UserDTO;
import com.cucn.springboot.controller.dto.UserPasswordDTO;
import com.cucn.springboot.exception.ServiceException;
import com.cucn.springboot.service.IMenuService;
import com.cucn.springboot.service.IUserService;
import com.cucn.springboot.entity.Menu;
import com.cucn.springboot.entity.Role;
import com.cucn.springboot.entity.User;
import com.cucn.springboot.mapper.RoleMapper;
import com.cucn.springboot.mapper.RoleMenuMapper;
import com.cucn.springboot.mapper.UserMapper;
import com.cucn.springboot.common.Constants;
import com.cucn.springboot.common.RoleEnum;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.cucn.springboot.utils.PasswordEncoderUtil;
import com.cucn.springboot.utils.TokenUtils;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.ArrayList;
import java.util.List;

/**
 * <p>
 *  服务实现类
 * </p>
 *
 * @author 青哥哥
 * @since 2022-01-26
 */
@Service
public class UserServiceImpl extends ServiceImpl<UserMapper, User> implements IUserService {

    private static final Log LOG = Log.get();

    @Resource
    private UserMapper userMapper;

    @Resource
    private RoleMapper roleMapper;

    @Resource
    private RoleMenuMapper roleMenuMapper;

    @Resource
    private IMenuService menuService;

    @Override
    public UserDTO login(UserDTO userDTO) {
        // Find user by username first
        // 先按用户名查询用户
        User one = getUserByUsername(userDTO.getUsername());
        if (one == null) {
            throw new ServiceException(Constants.CODE_600, "用户名或密码错误");
        }

        // Verify password using smart matching (BCrypt first, fallback to MD5)
        // 用智能匹配验证密码（先BCrypt，失败回退MD5）
        boolean passwordMatches = PasswordEncoderUtil.smartMatches(
                userDTO.getPassword(), one.getPassword());

        if (!passwordMatches) {
            throw new ServiceException(Constants.CODE_600, "用户名或密码错误");
        }

        // Auto-migrate legacy MD5 users to BCrypt on first successful login
        // 老用户首次登录成功后，自动把MD5密码升级为BCrypt
        if (PasswordEncoderUtil.needsMigration(one.getPassword())) {
            String newHash = PasswordEncoderUtil.encode(userDTO.getPassword());
            one.setPassword(newHash);
            updateById(one);
            LOG.info("User [{}] password migrated from MD5 to BCrypt", one.getUsername());
        }

        BeanUtil.copyProperties(one, userDTO, true);
        // Set token
        // 设置token
        String token = TokenUtils.genToken(one.getId().toString(), one.getPassword());
        userDTO.setToken(token);

        String role = one.getRole();
        // Set user's menu list
        // 设置用户的菜单列表
        List<Menu> roleMenus = getRoleMenus(role);
        userDTO.setMenus(roleMenus);
        return userDTO;
    }

    @Override
    public User register(UserDTO userDTO) {
        // Encode password with BCrypt
        // 用 BCrypt 加密密码
        String encodedPassword = PasswordEncoderUtil.encode(userDTO.getPassword());
        userDTO.setPassword(encodedPassword);

        User one = getUserByUsername(userDTO.getUsername());
        if (one == null) {
            one = new User();
            BeanUtil.copyProperties(userDTO, one, true);
            // Default role for new users is regular user
            // 新用户默认角色为普通用户
            String role = RoleEnum.ROLE_WORKER.toString();
            LambdaQueryWrapper<Role> roleLambdaQueryWrapper = new LambdaQueryWrapper<>();
            roleLambdaQueryWrapper.eq(Role::getFlag,role);
            Integer roleid = roleMapper.selectOne(roleLambdaQueryWrapper).getId();
            one.setRoleid(roleid);
            one.setRole(role);
            if (one.getNickname() == null) {
                one.setNickname(one.getUsername());
            }
            save(one);
        } else {
            throw new ServiceException(Constants.CODE_600, "用户已存在");
        }
        return one;
    }

    @Override
    public void updatePassword(UserPasswordDTO userPasswordDTO) {
        // Get current user from token
        // 从token获取当前用户
        User currentUser = TokenUtils.getCurrentUser();
        if (currentUser == null) {
            throw new ServiceException(Constants.CODE_401, "请先登录");
        }

        // Reload user from DB to get fresh password hash
        // 从数据库重新加载用户，拿到最新密码哈希
        User user = getById(currentUser.getId());
        if (user == null) {
            throw new ServiceException(Constants.CODE_600, "用户不存在");
        }

        // Verify old password
        // 验证旧密码
        boolean oldPasswordMatches = PasswordEncoderUtil.smartMatches(
                userPasswordDTO.getPassword(), user.getPassword());
        if (!oldPasswordMatches) {
            throw new ServiceException(Constants.CODE_600, "原密码错误");
        }

        // Encode new password with BCrypt and update
        // 用 BCrypt 加密新密码并更新
        String newHash = PasswordEncoderUtil.encode(userPasswordDTO.getNewPassword());
        user.setPassword(newHash);
        boolean updated = updateById(user);
        if (!updated) {
            throw new ServiceException(Constants.CODE_500, "密码更新失败");
        }
    }

    @Override
    public Page<User> findPage(Page<User> page, String username, String email, String address) {
        return userMapper.findPage(page, username, email, address);
    }


    @Override
    public void saveUpdateUser(User user) {
        LambdaQueryWrapper<Role> roleLambdaQueryWrapper = new LambdaQueryWrapper<>();
        String role = user.getRole();
        roleLambdaQueryWrapper.eq(Role::getFlag,role);
        Integer roleid = roleMapper.selectOne(roleLambdaQueryWrapper).getId();
        user.setRoleid(roleid);
        LambdaQueryWrapper<User> userLambdaQueryWrapper = new LambdaQueryWrapper<>();
        userLambdaQueryWrapper.eq(User::getId,user.getId());
        List<User> users = userMapper.selectList(userLambdaQueryWrapper);
        if (users.size()==0){
            userMapper.insert(user);
        }
        userMapper.updateById(user);
    }


    /**
     * Get user by username.
     * 按用户名查询用户。
     */
    private User getUserByUsername(String username) {
        QueryWrapper<User> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("username", username);
        User one;
        try {
            one = getOne(queryWrapper);
        } catch (Exception e) {
            LOG.error(e);
            throw new ServiceException(Constants.CODE_500, "系统错误");
        }
        return one;
    }

    /**
     * 获取当前角色的菜单列表
     * @param roleFlag
     * @return
     */
    private List<Menu> getRoleMenus(String roleFlag) {
        Integer roleId = roleMapper.selectByFlag(roleFlag);
        // 当前角色的所有菜单id集合
        List<Integer> menuIds = roleMenuMapper.selectByRoleId(roleId);

        // 查出系统所有的菜单(树形)
        List<Menu> menus = menuService.findMenus("");
        // new一个最后筛选完成之后的list
        List<Menu> roleMenus = new ArrayList<>();
        // 筛选当前用户角色的菜单
        for (Menu menu : menus) {
            if (menuIds.contains(menu.getId())) {
                roleMenus.add(menu);
            }
            List<Menu> children = menu.getChildren();
            // removeIf()  移除 children 里面不在 menuIds集合中的 元素
            children.removeIf(child -> !menuIds.contains(child.getId()));
        }
        return roleMenus;
    }



}
