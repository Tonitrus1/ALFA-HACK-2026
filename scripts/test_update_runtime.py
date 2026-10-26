import tempfile,unittest
from pathlib import Path
from update_runtime import compose_command
class UpdateRuntimeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();(self.root/'compose.yaml').write_text('services: {}');self.labels={'com.docker.compose.project':'existing-demo','com.docker.compose.project.config_files':str(self.root/'compose.yaml')}
 def test_preserves_project_and_base_file(self):
  cmd=compose_command(self.labels,self.root);self.assertEqual(cmd[:4],['docker','compose','--project-name','existing-demo']);self.assertIn(str(self.root/'compose.yaml'),cmd)
 def test_preserves_overlay_order(self):
  f=self.root/'local.yaml';f.write_text('services: {}');self.labels['com.docker.compose.project.config_files']+=','+str(f);self.assertEqual(compose_command(self.labels,self.root)[-4:],['-f',str(self.root/'compose.yaml'),'-f',str(f)])
 def test_preserves_recorded_environment_file(self):
  f=self.root/'.env.server';f.write_text('PRIVATE_KEY=not-output');self.labels['com.docker.compose.project.environment_file']=str(f);cmd=compose_command(self.labels,self.root);self.assertIn(str(f),cmd);self.assertNotIn('not-output',' '.join(cmd))
 def test_explicit_environment_file(self):
  f=self.root/'.env.server';f.write_text('');self.assertIn(str(f),compose_command(self.labels,self.root,Path('.env.server')))
 def test_refuses_wrong_checkout(self):
  with self.assertRaises(ValueError):compose_command(self.labels,self.root/'other')
 def test_refuses_missing_configuration(self):
  (self.root/'compose.yaml').unlink()
  with self.assertRaises(ValueError):compose_command(self.labels,self.root)
 def test_requires_selectel_env_if_not_recorded(self):
  f=self.root/'selectel';f.mkdir();(f/'compose.yaml').write_text('services: {}');self.labels['com.docker.compose.project.config_files']+=','+str(f/'compose.yaml')
  with self.assertRaises(ValueError):compose_command(self.labels,self.root)
