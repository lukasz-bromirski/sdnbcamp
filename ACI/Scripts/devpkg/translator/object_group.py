'''
Created on Dec 20, 2013

@author: dli
Copyright (c) 2013 by Cisco Systems
'''
from base.dmlist import DMList

class ObjectGroupList(DMList):
    """
    Model after object-group CLIs.
    This is a special DMList where the order of the children may not be quite right when first populated, in that
    a child referencing another child may come before the child being referenced due to the arbitrary order of
    Python dictionary. On generating CLI, we therefore, have to make sure a definition always come before the
    its reference.
    """
    def ifc2asa(self, no_asa_cfg_stack, asa_cfg_list):
        'Override the default implementation to make sure child referenced by other child comes in earlier'
        self.sort_children()
        DMList.ifc2asa(self, no_asa_cfg_stack, asa_cfg_list)

    def sort_children(self):
        'Make sure child referenced by other child comes in earlier'
        '#@todo: use validation to avoid cyclic reference'
        def reference(object_group, object_group_name):
            '@return True if object_group  directly or indirectly references an object group of name object_group_name; or False'
            def get_object_group(name):
                '@return a named object group'
                hits = filter(lambda child: child.get_value()['name'] == name, self.children.values())
                return hits[0] if hits else None

            group_objects = filter(lambda child: child.ifc_key == 'object_group_name', object_group.children.values())[0]
            for group_object in group_objects.children.values():
                if group_object.get_value() == object_group_name:
                    return True #directly referenced
                object_group = get_object_group(group_object.get_value())
                if not object_group:
                    self.log("ObjectGroupList.sort_children: '%s' referenced but has no definition." % group_object.get_value())
                    continue
                if reference(object_group, object_group_name):
                    return True #indirectly referenced
            return False

        def compare(x, y):
            if reference(x, y.get_value()['name']):
                result = 1
            elif reference(y, x.get_value()['name']):
                result = -1
            else:
                result = 0
            return result

        """
        @note: It would be simpler to use the builtin sorted function, like below:

            child_list = sorted(self.children.values(), cmp = compare)

        However, it does not work in case, CSCun10249, where one has three groups, such as A, B, C, and
        A references C, but B has no referential relationship with any one. Looks like for
        sorted function to work, its input must be total relation, i.e. every pair of its elements
        must be in referential relationship in this case.
        """

        child_list = []
        for child in self.children.values():
            references = filter(lambda x: compare(x, child) == 1, child_list)
            if references:
                index = child_list.index(references[0])
                child_list.insert(index, child)
            else:
                child_list.append(child)

        self.children.clear()
        for child in child_list:
            self.register_child(child)
