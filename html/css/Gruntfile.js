module.exports = function(grunt) {
  grunt.loadNpmTasks('grunt-contrib-less');
  require('jit-grunt')(grunt);

  grunt.initConfig({
    less: {
      development: {
        options: {
          compress: true,
          yuicompress: true,
          optimization: 2
        },
        files: {
          "social.css": "less/social.less", // destination file and source file
          "main.css": "less/main.less" // destination file and source file
        }
      }
    },
    watch: {
      styles: {
        files: ['less/social.less','less/main.less'], // which files to watch
        tasks: ['less'],
        options: {
          nospawn: true
        }
      }
    }
  });

  grunt.registerTask('default', ['less', 'watch']);
};